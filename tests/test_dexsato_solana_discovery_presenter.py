from presentation.dexsato_solana_discovery_presenter import (
    render_solana_discovery_page,
)


def test_solana_discovery_prototype_is_honest_and_read_only():
    html = render_solana_discovery_page()

    assert "Solana Discovery" in html
    assert "Evidence-led Solana intelligence" in html
    assert "Feed unavailable" in html
    assert "No discovery tokens are available yet." in html
    assert "Jupiter execution" in html
    assert "Planned, not active" in html
    assert "No wallet connection, quote or trade capability" in html
    assert "does not hold keys or funds" in html


def test_solana_discovery_has_search_filters_and_no_fake_candidates():
    html = render_solana_discovery_page()

    assert "Search token, symbol, or address" in html
    assert "New activity" in html
    assert ">Volume<" in html
    assert ">Liquidity<" in html
    assert "Tokens observed</span><strong>—" in html
    assert "Qualified now</span><strong>—" in html
    assert "data-token-address" not in html


def test_solana_discovery_is_responsive_and_supports_existing_themes():
    html = render_solana_discovery_page()

    assert "@media(max-width:820px)" in html
    assert "@media(max-width:480px)" in html
    assert 'data-theme-option="current"' in html
    assert 'data-theme-option="plain"' in html
    assert 'aria-label="Use current dark theme"' in html
    assert 'aria-label="Use plain white theme"' in html
    assert 'href="/"' in html


def test_solana_discovery_uses_market_terminal_layout():
    html = render_solana_discovery_page()

    assert "Solana Discovery Terminal" in html
    assert 'class="workspace"' in html
    assert 'class="feed-panel"' in html
    assert 'class="intel-rail"' in html
    assert "Qualification rules" in html
    assert "Pool verification is not token verification" in html
    assert "Discovery rank reflects activity, not safety." in html
    assert "grid-template-columns:minmax(0,1fr) 310px" in html


def test_solana_discovery_uses_terminal_typography_stack():
    html = render_solana_discovery_page()

    assert '"Bahnschrift SemiBold"' in html
    assert '"Cascadia Mono"' in html
    assert "font-family:var(--font-display)" in html
    assert "font-family:var(--font-mono)" in html


def test_solana_discovery_enlarges_terminal_detail_text():
    html = render_solana_discovery_page()

    assert ".feed-head h2{font-size:24px" in html
    assert ".token-cell strong{font-size:18px}" in html
    assert ".market-cell strong{font-size:15px}" in html
    assert ".evidence-cell p{font-size:12px" in html
    assert ".rail-card h3{font-size:16px" in html


def test_solana_discovery_candidates_open_internal_token_workspace():
    html = render_solana_discovery_page({
        "connected": True, "fresh": True, "candidates": [{
            "token_address": "TokenAddressCaseSensitive123",
            "pair_address": "PoolAddress123", "symbol": "TEST",
        }],
    })

    assert 'href="/discovery/solana/TokenAddressCaseSensitive123"' in html
    assert "Open workspace" in html


def test_solana_discovery_renders_connected_telemetry_without_candidates():
    html = render_solana_discovery_page({
        "connected": True,
        "collector_status": "Running",
        "tokens_observed": 4742,
        "pair_resolved": 3271,
        "qualified_candidates": None,
        "updated_label": "5 min ago",
        "message": "Collector telemetry is connected; publication remains disabled.",
    })

    assert "Collector connected" in html
    assert "Tokens observed</span><strong>4742" in html
    assert "Pairs resolved</span><strong>3271" in html
    assert "Qualified now</span><strong>—" in html
    assert "5 min ago" in html


def test_solana_discovery_renders_qualified_candidate_and_explicit_risk():
    html = render_solana_discovery_page({
        "connected": True,
        "tokens_observed": 4742,
        "pair_resolved": 3271,
        "qualified_candidates": 1,
        "candidates": [{
            "name": "Example token", "symbol": "EX", "quote_symbol": "SOL",
            "token_address": "token-address", "pair_address": "pool-address",
            "dex_id": "raydium", "price_usd": 0.25, "liquidity_usd": 12000,
            "volume_24h_usd": 4500, "pair_age": "3h",
            "evidence": "Verified Solana pool with observable liquidity and 24h activity.",
            "risk_label": "Token security not independently verified",
        }],
    })

    assert "Qualified now</span><strong>1" in html
    assert "Example token" in html and "EX / SOL" in html
    assert "$12.00K" in html and "$4.50K" in html
    assert "Token security not independently verified" in html
    assert "data-token-address=\"token-address\"" in html
    assert "Observed activity" in html
    assert "Inspect pool" not in html
    assert "Pool pool-address" in html
