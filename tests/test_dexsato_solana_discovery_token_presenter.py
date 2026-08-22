from presentation.dexsato_solana_discovery_token_presenter import render_solana_discovery_token_page


DETAIL = {
    "token_address": "TokenAddress123456789", "pair_address": "PoolAddress123456789",
    "symbol": "TEST", "name": "Test Token", "quote_symbol": "SOL",
    "dex_id": "raydium", "price_usd": .12, "change_24h": 4.5,
    "liquidity_usd": 7000, "volume_24h_usd": 3000, "market_cap": 120000,
    "pair_age": "2h", "quote_status": "LIVE", "quote_label": "Live exact-pool observation",
    "evidence": "Observed liquidity and activity.", "risk_label": "Security unavailable",
    "source_url": "https://dexscreener.com/solana/pool", "feed_updated_label": "4 min ago",
    "chart": [
        {"close": .10}, {"close": .11}, {"close": .105},
        {"close": .115}, {"close": .108}, {"close": .12},
    ],
}


def test_renders_exact_token_workspace_and_chart():
    html = render_solana_discovery_token_page(DETAIL)
    assert "Qualified exact-token workspace" in html
    assert "TEST / SOL" in html
    assert "Validated exact-pool data" in html
    assert "aria-label=\"Validated exact-pool 4H closing-price chart\"" in html
    assert "Live exact-pool observation" in html
    assert "Open market source" in html
    assert 'src="/static/branding/dexsato-logo.png"' in html
    assert 'data-copy-address="TokenAddress123456789"' in html
    assert 'data-copy-address="PoolAddress123456789"' in html


def test_keeps_jupiter_read_only_and_discloses_risk():
    html = render_solana_discovery_token_page(DETAIL)
    assert "Planned, not active" in html
    assert "No wallet connection, executable quote or swap is enabled" in html
    assert "Pool verification is not token verification" in html
    assert "does not hold private keys or funds" in html


def test_chart_fails_safely_when_unavailable():
    html = render_solana_discovery_token_page({**DETAIL, "chart": []})
    assert "Insufficient chart history" in html
    assert "Only 0 closed 4H candles available" in html


def test_chart_does_not_imply_a_trend_from_two_candles():
    html = render_solana_discovery_token_page({
        **DETAIL, "chart": [{"close": .12}, {"close": .08}],
    })

    assert "Only 2 closed 4H candles available" in html
    assert "At least 6 are required" in html
    assert "<polyline" not in html
