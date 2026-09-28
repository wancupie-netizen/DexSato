from uuid import uuid4

from application.product_identity_models import ProductPrincipal
from application.product_entitlement_policy import PRO_ENTITLEMENTS, PUBLIC_ENTITLEMENTS
from application.product_surface_entitlement import locked_discovery_feed, locked_recent_feed
from presentation.dexsato_solana_discovery_presenter import render_solana_discovery_page


_CONTEXT = {
    "dex_card": {
        "volume": "$1.00B",
        "change": "+1.0%",
        "change_class": " up",
        "tvl": "$1.00B",
        "state": "LIVE",
        "dot_class": " live",
        "line_path": "M0 0 L1 1",
        "area_path": "M0 0 L1 1 Z",
    },
    "perps_volume_24h": "$1.00M",
    "priority_fee": ("Gas · Low", " low"),
}


def test_market_page_is_visually_inert_while_product_auth_is_disabled():
    html = render_solana_discovery_page(presenter_context=_CONTEXT)
    assert "Wallet Profile" in html
    assert 'href="/login"' not in html


def test_market_page_shows_sign_in_only_when_product_auth_is_available():
    html = render_solana_discovery_page(
        presenter_context=_CONTEXT,
        product_auth_available=True,
        product_principal=ProductPrincipal.guest(),
    )
    assert 'href="/login">Sign In</a>' in html
    assert "Wallet Profile" not in html


def test_market_page_shows_masked_account_and_logout_without_raw_email():
    html = render_solana_discovery_page(
        presenter_context=_CONTEXT,
        product_auth_available=True,
        product_principal=ProductPrincipal(True, uuid4(), "u***@example.com"),
    )
    assert "u***@example.com" in html
    assert "user@example.com" not in html
    assert 'id="dex-product-logout"' in html
    assert 'fetch("/logout"' in html

def test_market_page_tier_label_comes_from_server_policy():
    user = ProductPrincipal(True, uuid4(), "u***@example.com")
    public = render_solana_discovery_page(
        presenter_context=_CONTEXT, product_auth_available=True,
        product_principal=user, product_policy=PUBLIC_ENTITLEMENTS,
    )
    pro = render_solana_discovery_page(
        presenter_context=_CONTEXT, product_auth_available=True,
        product_principal=user, product_policy=PRO_ENTITLEMENTS,
    )
    assert 'aria-label="Public access">PUBLIC</span>' in public
    assert 'aria-label="Pro access">PRO</span>' in pro
    assert 'aria-label="Pro access">PRO</span>' not in public


def test_public_locked_surfaces_explain_pro_access_without_empty_feed_claims():
    html = render_solana_discovery_page(
        locked_discovery_feed(),
        recent=locked_recent_feed(),
        presenter_context=_CONTEXT,
        product_auth_available=True,
        product_principal=ProductPrincipal(True, uuid4(), "u***@example.com"),
        product_policy=PUBLIC_ENTITLEMENTS,
    )
    assert "Full Discovery and Archive requires Pro access" in html
    assert "Recent 24H requires Pro access" in html
    assert "Upgrades are not available here yet." in html
    assert "No eligible Recent tokens displayed" not in html
    assert "No tokens qualified in the last 24 hours." not in html
    assert 'href="/login">Sign in</a>' not in html


def test_guest_locked_surfaces_offer_sign_in_only_when_auth_is_available():
    guest = ProductPrincipal.guest()
    available = render_solana_discovery_page(
        locked_discovery_feed(),
        recent=locked_recent_feed(),
        presenter_context=_CONTEXT,
        product_auth_available=True,
        product_principal=guest,
        product_policy=PUBLIC_ENTITLEMENTS,
    )
    disabled = render_solana_discovery_page(
        locked_discovery_feed(),
        recent=locked_recent_feed(),
        presenter_context=_CONTEXT,
        product_auth_available=False,
        product_principal=guest,
        product_policy=PUBLIC_ENTITLEMENTS,
    )
    assert available.count('href="/login">Sign in</a>') == 2
    assert 'href="/login">Sign in</a>' not in disabled


def test_pro_unlocked_empty_feeds_do_not_show_access_lock():
    html = render_solana_discovery_page(
        {"candidates": [], "view": "rolling"},
        recent={"rows": []},
        presenter_context=_CONTEXT,
        product_auth_available=True,
        product_principal=ProductPrincipal(True, uuid4(), "u***@example.com"),
        product_policy=PRO_ENTITLEMENTS,
    )
    assert "requires Pro access" not in html
    assert "No eligible Recent tokens displayed" in html
    assert "No tokens qualified in the last 24 hours." in html