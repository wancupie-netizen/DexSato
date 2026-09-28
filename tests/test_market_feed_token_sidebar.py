import pytest

from presentation.dexsato_market_feed_token_presenter import (
    render_organic_flow_token_page,
    render_recent_token_page,
    render_top_traded_token_page,
    render_trending_token_page,
)
from presentation.dexsato_solana_discovery_token_presenter import (
    render_solana_discovery_token_page,
)


DETAIL = {
    "token_address": "TokenAddress123456789",
    "pair_address": "PoolAddress123456789",
    "symbol": "TEST",
    "name": "Test Token",
    "quote_symbol": "SOL",
}
FEED = {"candidates": [DETAIL]}


@pytest.mark.parametrize(
    "render",
    (
        render_recent_token_page,
        render_organic_flow_token_page,
        render_top_traded_token_page,
        render_trending_token_page,
    ),
)
def test_market_workspace_uses_home_sidebar_and_own_api(render):
    html = render(DETAIL, feed=FEED)

    assert 'href="/" aria-label="Solana" title="Solana"' in html
    assert 'href="/discovery/solana" aria-label="Solana"' not in html
    assert 'data-api-base="/api/market/' in html
    assert '<section class="discovery-engine-v12"' not in html


def test_legacy_discovery_workspace_still_links_to_legacy_route():
    html = render_solana_discovery_token_page(DETAIL, feed=FEED)

    assert 'href="/discovery/solana" aria-label="Solana"' in html
