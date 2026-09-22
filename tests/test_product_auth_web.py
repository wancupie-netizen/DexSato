from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from application.product_auth_web import (
    PRODUCT_SESSION_COOKIE,
    delete_product_session_cookie,
    product_cookie_secure,
    require_same_origin,
    set_product_session_cookie,
)


def _request(*, scheme="http", host="testserver", origin="http://testserver", forwarded=""):
    headers = {"host": host, "origin": origin}
    if forwarded:
        headers["x-forwarded-proto"] = forwarded
    return SimpleNamespace(url=SimpleNamespace(scheme=scheme), headers=headers)


def test_same_origin_accepts_exact_local_origin_and_rejects_cross_site():
    with patch.dict("os.environ", {}, clear=True):
        assert require_same_origin(_request()) is None
        with pytest.raises(HTTPException) as captured:
            require_same_origin(_request(origin="https://attacker.example"))
    assert captured.value.status_code == 403


def test_product_cookie_is_always_secure_in_production_and_only_trusts_configured_proxy():
    with patch.dict("os.environ", {"DEXSATO_ENV": "production"}, clear=True):
        assert product_cookie_secure(_request()) is True
    with patch.dict("os.environ", {"DEXSATO_TRUST_PROXY_HEADERS": "false"}, clear=True):
        assert product_cookie_secure(_request(forwarded="https")) is False
    with patch.dict("os.environ", {"DEXSATO_TRUST_PROXY_HEADERS": "true"}, clear=True):
        assert product_cookie_secure(_request(forwarded="https")) is True


def test_product_cookie_is_host_only_http_only_and_removed_with_matching_scope():
    request = _request()
    with patch.dict("os.environ", {}, clear=True):
        response = JSONResponse({"status": "ok"})
        set_product_session_cookie(
            response,
            request,
            token="opaque-session-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        header = response.headers["set-cookie"]
        assert header.startswith(f"{PRODUCT_SESSION_COOKIE}=opaque-session-token;")
        assert "HttpOnly" in header
        assert "Path=/" in header
        assert "SameSite=lax" in header
        assert "Domain=" not in header

        cleared = JSONResponse({"status": "ok"})
        delete_product_session_cookie(cleared, request)
        cleared_header = cleared.headers["set-cookie"]
        assert cleared_header.startswith(f'{PRODUCT_SESSION_COOKIE}="";')
        assert "Max-Age=0" in cleared_header
        assert "Path=/" in cleared_header

