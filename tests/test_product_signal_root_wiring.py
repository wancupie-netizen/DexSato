from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from fastapi.responses import HTMLResponse

from application.product_auth_routes import ProductAuthView
from application.product_entitlement_policy import PRO_ENTITLEMENTS, PUBLIC_ENTITLEMENTS
from application.product_guest_identity import (
    PRODUCT_GUEST_COOKIE,
    ProductGuestIdentity,
)
from application.product_identity_models import ProductPrincipal
from application.product_signal_entitlement import (
    ProductSignalEntitlementAdmission,
    apply_detected_signal_entitlements,
)
from application.product_signal_quota_store import ProductSignalQuotaStoreUnavailable
from app import main as app_main


GUEST_ID = UUID("22222222-2222-4222-8222-222222222222")
USER_ID = UUID("11111111-1111-4111-8111-111111111111")


def _request(*, guest_cookie=None):
    cookies = {}
    if guest_cookie is not None:
        cookies[PRODUCT_GUEST_COOKIE] = guest_cookie
    return SimpleNamespace(
        cookies=cookies,
        url=SimpleNamespace(scheme="https"),
        headers={},
    )


def _signal(label: str) -> dict[str, object]:
    return {
        "primary_signal": label,
        "secondary_evidence": ["Volume up"],
        "direction": "bullish",
    }


def _feeds() -> dict[str, dict[str, object]]:
    return {
        "trending": {
            "rows": [
                {"token_address": "MintA", "rank": 1, "detected_signal": _signal("A")},
                {"token_address": "MintB", "rank": 2, "detected_signal": _signal("B")},
            ]
        },
        "top_traded": {"rows": []},
        "organic_flow": {"rows": []},
        "recent": {"rows": []},
    }


def _admission(*allowed: str, quota_limit=5) -> ProductSignalEntitlementAdmission:
    return ProductSignalEntitlementAdmission(
        allowed_token_addresses=tuple(allowed),
        newly_admitted_token_addresses=tuple(allowed),
        quota_limit=quota_limit,
        active_count=len(allowed) if quota_limit is not None else None,
        remaining=(max(0, quota_limit - len(allowed)) if quota_limit is not None else None),
    )


def _patch_root_dependencies(auth_view, policy, feeds):
    return (
        patch("app.main._request_entitlement_policy", return_value=(auth_view, policy)),
        patch("app.main._load_discovery_page_context", return_value=(feeds, {"ctx": True})),
        patch("app.main.apply_market_feed_entitlements", side_effect=lambda value, _: value),
        patch("app.main.locked_discovery_feed", return_value={"locked": True}),
        patch("app.main.load_solana_discovery_feed", return_value={"full": True}),
        patch("app.main.render_solana_discovery_page", return_value="<html>root</html>"),
    )


def test_public_guest_root_applies_quota_projection_and_sets_new_guest_cookie():
    request = _request()
    auth_view = ProductAuthView(True, ProductPrincipal.guest())
    feeds = _feeds()
    dependencies = _patch_root_dependencies(auth_view, PUBLIC_ENTITLEMENTS, feeds)

    with dependencies[0], dependencies[1], dependencies[2], dependencies[3], dependencies[4], dependencies[5] as render, patch(
        "app.main.resolve_product_guest_identity",
        return_value=ProductGuestIdentity(GUEST_ID, True),
    ), patch(
        "app.main.apply_detected_signal_entitlements",
        return_value=_admission("MintA"),
    ) as apply_signals:
        response = app_main.app_home(request)

    assert isinstance(response, HTMLResponse)
    assert response.body == b"<html>root</html>"
    apply_signals.assert_called_once_with(
        ("MintA", "MintB"),
        PUBLIC_ENTITLEMENTS,
        subject_key=f"guest:{GUEST_ID}",
    )
    rendered = render.call_args.kwargs
    assert "detected_signal" in rendered["trending"]["rows"][0]
    assert "detected_signal" not in rendered["trending"]["rows"][1]
    assert response.headers["set-cookie"].startswith(f"{PRODUCT_GUEST_COOKIE}={GUEST_ID};")


def test_existing_guest_cookie_is_reused_without_set_cookie_rotation():
    request = _request(guest_cookie=str(GUEST_ID))
    auth_view = ProductAuthView(True, ProductPrincipal.guest())
    feeds = _feeds()
    dependencies = _patch_root_dependencies(auth_view, PUBLIC_ENTITLEMENTS, feeds)

    with dependencies[0], dependencies[1], dependencies[2], dependencies[3], dependencies[4], dependencies[5], patch(
        "app.main.apply_detected_signal_entitlements",
        return_value=_admission("MintA"),
    ) as apply_signals:
        response = app_main.app_home(request)

    apply_signals.assert_called_once_with(
        ("MintA", "MintB"),
        PUBLIC_ENTITLEMENTS,
        subject_key=f"guest:{GUEST_ID}",
    )
    assert "set-cookie" not in response.headers


def test_authenticated_public_root_uses_user_subject_without_guest_cookie_resolution():
    request = _request()
    principal = ProductPrincipal(
        authenticated=True,
        user_id=USER_ID,
        email_masked="u***@example.com",
    )
    auth_view = ProductAuthView(True, principal)
    feeds = _feeds()
    dependencies = _patch_root_dependencies(auth_view, PUBLIC_ENTITLEMENTS, feeds)

    with dependencies[0], dependencies[1], dependencies[2], dependencies[3], dependencies[4], dependencies[5], patch(
        "app.main.resolve_product_guest_identity",
        side_effect=AssertionError("authenticated principal must not resolve guest identity"),
    ), patch(
        "app.main.apply_detected_signal_entitlements",
        return_value=_admission("MintA"),
    ) as apply_signals:
        response = app_main.app_home(request)

    apply_signals.assert_called_once_with(
        ("MintA", "MintB"),
        PUBLIC_ENTITLEMENTS,
        subject_key=f"user:{USER_ID}",
    )
    assert "set-cookie" not in response.headers


def test_pro_root_bypasses_subject_and_quota_ledger_while_preserving_signals():
    request = _request()
    principal = ProductPrincipal(
        authenticated=True,
        user_id=USER_ID,
        email_masked="u***@example.com",
    )
    auth_view = ProductAuthView(True, principal)
    feeds = _feeds()
    dependencies = _patch_root_dependencies(auth_view, PRO_ENTITLEMENTS, feeds)

    with dependencies[0], dependencies[1], dependencies[2], dependencies[3], dependencies[4], dependencies[5] as render, patch(
        "app.main.resolve_product_guest_identity",
        side_effect=AssertionError("Pro must not resolve guest identity"),
    ), patch(
        "app.main.product_signal_quota_subject_key",
        side_effect=AssertionError("Pro must not build a quota subject"),
    ), patch(
        "app.main.apply_detected_signal_entitlements",
        wraps=apply_detected_signal_entitlements,
    ) as apply_signals:
        response = app_main.app_home(request)

    apply_signals.assert_called_once_with(
        ("MintA", "MintB"),
        PRO_ENTITLEMENTS,
        subject_key=None,
    )
    rendered = render.call_args.kwargs
    assert "detected_signal" in rendered["trending"]["rows"][0]
    assert "detected_signal" in rendered["trending"]["rows"][1]
    assert "set-cookie" not in response.headers


def test_quota_store_failure_hides_signals_but_keeps_root_page_available():
    request = _request()
    auth_view = ProductAuthView(True, ProductPrincipal.guest())
    feeds = _feeds()
    dependencies = _patch_root_dependencies(auth_view, PUBLIC_ENTITLEMENTS, feeds)

    with dependencies[0], dependencies[1], dependencies[2], dependencies[3], dependencies[4], dependencies[5] as render, patch(
        "app.main.resolve_product_guest_identity",
        return_value=ProductGuestIdentity(GUEST_ID, True),
    ), patch(
        "app.main.apply_detected_signal_entitlements",
        side_effect=ProductSignalQuotaStoreUnavailable("quota unavailable"),
    ):
        response = app_main.app_home(request)

    assert response.status_code == 200
    rendered = render.call_args.kwargs
    assert all(
        "detected_signal" not in row
        for row in rendered["trending"]["rows"]
    )
    assert response.headers["set-cookie"].startswith(f"{PRODUCT_GUEST_COOKIE}={GUEST_ID};")


def test_root_only_wires_detected_signal_quota_before_presenter():
    source = Path("app/main.py").read_text(encoding="utf-8")
    home_start = source.index("def app_home(request: Request)")
    home_end = source.index("# TEMP-HIDE-MAJOR-ASSETS-01", home_start)
    home = source[home_start:home_end]
    solana_start = source.index("def solana_discovery(request: Request", home_end)
    solana_end = source.index("@app.get(\n    \"/discovery/solana/{token_address}\"", solana_start)
    solana = source[solana_start:solana_end]

    assert home.index("apply_market_feed_entitlements(") < home.index(
        "_apply_root_detected_signal_entitlements("
    ) < home.index("render_solana_discovery_page(")
    assert "_apply_root_detected_signal_entitlements(" not in solana
    assert source.count("market_feeds = apply_market_feed_entitlements(") == 2
