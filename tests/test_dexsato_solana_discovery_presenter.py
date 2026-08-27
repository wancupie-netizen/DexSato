from presentation.dexsato_solana_discovery_presenter import (
    render_solana_discovery_page,
)


def test_solana_discovery_prototype_is_honest_and_read_only():
    html = render_solana_discovery_page()

    assert "Solana Discovery" in html
    assert "Evidence-led Solana intelligence" in html
    assert "Feed unavailable" in html
    assert "No token currently meets all qualification requirements." in html
    assert "Network activity" in html
    assert "Observed 24h Volume" in html
    assert "Coming soon" in html and "Multiple chain" in html


def test_solana_discovery_has_persistent_views_and_no_fake_candidates():
    html = render_solana_discovery_page()

    assert "Qualified Now" in html
    assert "Recent Discoveries" in html
    assert "Full Archive" in html
    assert "25 per page" in html
    assert "data-token-address" not in html


def test_solana_discovery_is_responsive_and_supports_existing_themes():
    html = render_solana_discovery_page()

    assert "@media(max-width:820px)" in html
    assert "@media(max-width:480px)" in html
    assert 'data-theme-option="current"' in html
    assert 'data-theme-option="intel"' in html
    assert 'aria-label="Use market intelligence theme"' in html
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
    assert "Network activity" in html
    assert "Observed qualified pools" in html
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
    assert "Open Analysis" in html


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
    assert "Qualified Now</span><strong>—" in html
    assert "5 min ago" in html


def test_solana_discovery_renders_qualified_candidate_in_compact_feed():
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

    assert "Qualified Now</span><strong>1" in html
    assert "Example token" in html and "EX / SOL" in html
    assert "$12.00K" in html and "$4.50K" in html
    assert "data-token-address=\"token-address\"" in html
    assert "Inspect pool" not in html
    assert "Pool pool-address" not in html

def test_solana_discovery_v32_feed_is_compact_and_decision_focused():
    html = render_solana_discovery_page({
        "connected": True,
        "fresh": True,
        "qualified_candidates": 1,
        "candidates": [{
            "name": "Example token",
            "symbol": "EX",
            "quote_symbol": "SOL",
            "token_address": "token-address",
            "pair_address": "pool-address",
            "dex_id": "raydium",
            "price_usd": 0.25,
            "liquidity_usd": 12000,
            "volume_24h_usd": 45000,
            "pair_age": "2h",
            "evidence": "Verbose evidence belongs in token workspace.",
            "risk_label": "Verbose risk belongs in token workspace",
        }],
    })

    assert "EX / SOL" in html
    assert "Price" in html
    assert "Liquidity" in html
    assert "24h Vol" in html
    assert "Age" in html
    assert "Observation" in html
    assert "Previously qualified" in html
    assert "Open Analysis" in html
    assert "Verbose evidence belongs in token workspace." not in html
    assert "Verbose risk belongs in token workspace" not in html
    assert "candidate-row-v32" in html

def test_solana_discovery_v33_feed_uses_safe_ascii_and_compact_header():
    html = render_solana_discovery_page({
        "connected": True,
        "fresh": True,
        "qualified_candidates": 1,
        "candidates": [{
            "name": "Example token",
            "symbol": "EX",
            "quote_symbol": "SOL",
            "token_address": "token-address",
            "pair_address": "pool-address",
            "dex_id": "raydium",
            "price_usd": 0.25,
            "liquidity_usd": 12000,
            "volume_24h_usd": 45000,
            "pair_age": "2h",
        }],
    })

    assert 'class="feed-columns-v33"' in html
    assert "Observation" in html
    assert "Open Analysis &rarr;" in html
    assert "Previously qualified" in html
    assert "Â· exact pool" not in html

def test_solana_discovery_mi_v34_has_clean_feed_font_dot_and_metric_icons():
    html = render_solana_discovery_page({
        "connected": True,
        "fresh": True,
        "qualified_candidates": 1,
        "candidates": [{
            "name": "Example token",
            "symbol": "EX",
            "quote_symbol": "SOL",
            "token_address": "token-address",
            "pair_address": "pool-address",
            "dex_id": "raydium",
            "price_usd": 0.25,
            "liquidity_usd": 12000,
            "volume_24h_usd": 45000,
            "pair_age": "2h",
        }],
    })

    assert "Observed market activity" in html
    assert 'class="why-dot"' in html
    assert 'class="metric metric-observed"' in html
    assert 'class="metric metric-resolved"' in html
    assert 'class="metric metric-qualified"' in html
    assert 'class="metric metric-network"' in html
    assert 'font-family:Inter,"Segoe UI Variable Text"' in html


def test_solana_discovery_v29a_has_pagination_and_observed_network_facts():
    html = render_solana_discovery_page({
        "connected": True, "fresh": True, "qualified_candidates": 2,
        "qualified_total": 2, "recent_total": 5, "archive_total": 61,
        "view": "archive", "page": 3, "page_count": 3, "page_size": 25,
        "observed_volume_24h_usd": 12_345, "observed_txns_24h": 99,
        "observed_dex_ids": ["pumpswap", "raydium"], "candidates": [],
    })
    assert "25 per page · Page 3 of 3" in html
    assert "$12.35K" in html and ">99<" in html
    assert "pumpswap" in html and "raydium" in html
    assert "Archive Context" not in html


def test_solana_discovery_v291_explains_zero_qualification_without_broken_link():
    html = render_solana_discovery_page({
        "connected": True, "fresh": True, "qualified_candidates": 0,
        "qualified_total": 0, "recent_total": 71, "archive_total": 202,
        "view": "qualified", "page": 1, "page_count": 1, "page_size": 25,
        "observed_volume_24h_usd": 0, "observed_txns_24h": 0,
        "observed_dex_ids": [], "candidates": [],
    })
    assert "No token currently meets all qualification requirements." in html
    assert "View Recent Discoveries" in html and "Open Full Archive" in html
    assert "preparing its first validated feed" not in html
    assert "#qualification-rules" not in html
    assert "Observed 24h Volume</span><strong>$0.00" in html
    assert "Observed 24H Txns</span><strong>0" in html
    assert "None currently observed" in html


def test_solana_discovery_v292_renders_server_search_and_sort_clarity():
    html = render_solana_discovery_page({
        "connected": True, "fresh": True, "view": "archive", "page": 2,
        "page_count": 4, "page_size": 25, "view_total": 76,
        "qualified_total": 2, "recent_total": 10, "archive_total": 202,
        "search_query": "BER mint", "search_counts": {"qualified": 1, "recent": 3, "archive": 76},
        "candidates": [],
    })
    assert 'name="q" value="BER mint"' in html
    assert "Search token, symbol, contract or DEX" in html
    assert "Sorted by: Last qualified" in html
    assert "76 matching observations" in html
    assert "view=recent&page=1&q=BER%20mint" in html
    assert "No matching token found." in html
    assert "Clear search" in html
