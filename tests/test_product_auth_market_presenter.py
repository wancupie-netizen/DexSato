from uuid import uuid4

from application.product_identity_models import ProductPrincipal
from application.product_entitlement_policy import PRO_ENTITLEMENTS, PUBLIC_ENTITLEMENTS
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
