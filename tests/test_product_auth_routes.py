from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.product_auth_provider import VerifiedProductIdentity
from application.product_auth_routes import router
from application.product_identity_models import IssuedProductSession, ProductPrincipal


def _environment():
    return {
        "DEXSATO_PRODUCT_AUTH_ENABLED": "true",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
        "SUPABASE_SECRET_KEY": "sb_secret_test",
    }


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_product_auth_routes_are_hidden_while_gate_is_disabled():
    with patch.dict("os.environ", {}, clear=True):
        response = _client().get("/login")
    assert response.status_code == 404


def test_login_page_is_available_only_after_runtime_configuration_passes():
    with patch.dict("os.environ", _environment(), clear=True):
        response = _client().get("/login")
    assert response.status_code == 200
    assert "Sign in to DexSato" in response.text


def test_otp_request_requires_same_origin_and_returns_generic_acceptance():
    provider = SimpleNamespace(request_email_otp=lambda **kwargs: None)
    with (
        patch.dict("os.environ", _environment(), clear=True),
        patch("application.product_auth_routes.build_product_auth_provider", return_value=provider),
    ):
        rejected = _client().post(
            "/auth/otp/request",
            headers={"origin": "https://attacker.example"},
            json={"email": "user@example.com"},
        )
        accepted = _client().post(
            "/auth/otp/request",
            headers={"origin": "http://testserver"},
            json={"email": " User@Example.com "},
        )
    assert rejected.status_code == 403
    assert accepted.status_code == 202
    assert accepted.json() == {
        "status": "accepted",
        "message": "If delivery is available, check your email.",
    }


def test_otp_verify_sets_only_opaque_dexsato_cookie():
    provider = SimpleNamespace(
        verify_email_otp=lambda **kwargs: VerifiedProductIdentity(
            auth_provider="supabase",
            auth_subject="provider-user-1",
            email="user@example.com",
        )
    )
    issued = IssuedProductSession(
        token="opaque-product-token",
        principal=ProductPrincipal(True, uuid4(), "u***@example.com"),
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    service = SimpleNamespace(create_authenticated_session=lambda **kwargs: issued)
    with (
        patch.dict("os.environ", _environment(), clear=True),
        patch("application.product_auth_routes.build_product_auth_provider", return_value=provider),
        patch("application.product_auth_routes.build_product_identity_service", return_value=service),
    ):
        response = _client().post(
            "/auth/otp/verify",
            headers={"origin": "http://testserver"},
            json={"email": "user@example.com", "code": "123456"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "redirect": "/"}
    cookie = response.headers["set-cookie"]
    assert "dexsato_product_session=opaque-product-token" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "access_token" not in cookie
    assert "refresh_token" not in cookie


def test_logout_revokes_server_session_and_clears_cookie():
    seen = []
    service = SimpleNamespace(logout=lambda token: seen.append(token) or True)
    with (
        patch.dict("os.environ", _environment(), clear=True),
        patch("application.product_auth_routes.build_product_identity_service", return_value=service),
    ):
        response = _client().post(
            "/logout",
            headers={"origin": "http://testserver"},
            cookies={"dexsato_product_session": "opaque-product-token"},
            json={},
        )
    assert response.status_code == 200
    assert seen == ["opaque-product-token"]
    assert "Max-Age=0" in response.headers["set-cookie"]

