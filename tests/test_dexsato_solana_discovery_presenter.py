import pytest

import presentation.dexsato_solana_discovery_presenter as discovery_presenter


render_solana_discovery_page = discovery_presenter.render_solana_discovery_page


@pytest.fixture(autouse=True)
def _isolate_presenter_from_public_market_endpoints(monkeypatch):
    """Keep presenter characterization deterministic and presentation-only."""
    monkeypatch.setattr(
        discovery_presenter,
        "_solana_dex_card_metrics",
        lambda: {
            "volume": "—",
            "change": "—",
            "change_class": "",
            "tvl": "—",
            "state": "UNAVAILABLE",
            "dot_class": " is-offline",
            "line_path": "",
            "area_path": "",
        },
    )
    monkeypatch.setattr(discovery_presenter, "_solana_perps_volume_24h", lambda: "—")
    monkeypatch.setattr(
        discovery_presenter,
        "_solana_priority_fee",
        lambda: ("Gas · —", " is-offline"),
    )


def test_solana_discovery_prototype_is_honest_and_read_only():
    html = render_solana_discovery_page()

    assert "Solana Discovery" in html
    assert "TOTAL DEX VOLUME · 24H · SOLANA" in html
    assert "LIVE SIGNALS" in html
    assert "No signal data displayed yet" in html
    assert "No tokens qualified in the last 24 hours." in html
    assert "Experimental discovery · evidence synthesis only · not financial advice." in html
    assert "Get buy quote" not in html


def test_solana_discovery_hides_legacy_views_and_has_no_fake_candidates():
    html = render_solana_discovery_page()

    assert "Qualified Now" not in html
    assert "Recent Discoveries" not in html
    assert "Full Archive" not in html
    assert "Page 1 of 1" not in html
    assert 'class="sort-note"' not in html
    assert 'class="feed-columns-v33"' not in html
    assert '<form class="terminal-search"' not in html
    assert 'href="/discovery/solana?view=recent' not in html
    assert 'href="/discovery/solana?view=archive' not in html
    assert '<nav class="discovery-segments-v1"' not in html
    assert "data-token-address" not in html


def test_solana_discovery_is_responsive_and_preserves_dark_terminal_tokens():
    html = render_solana_discovery_page()

    assert "@media(max-width:820px)" in html
    assert "@media(max-width:480px)" in html
    assert "color-scheme:dark" in html
    assert "--bg:#070b12" in html
    assert "--cyan:#14f1d9" in html
    assert 'href="/"' in html
    assert 'href="/major-assets"' not in html


def test_solana_discovery_uses_market_terminal_layout():
    html = render_solana_discovery_page()

    assert "Solana Discovery Terminal" in html
    assert 'class="dex-app-shell"' in html
    assert 'class="dex-side-rail"' in html
    assert 'class="dex-app-main"' in html
    assert 'class="dex-volume-panel"' in html
    assert "dex-signals-panel" in html
    assert 'class="dex-market-category-shell"' in html
    assert 'class="dex-market-tabs"' in html
    assert "dex-market-intelligence" in html
    assert "dex-token-list" in html
    assert 'class="feed-panel"' in html


def test_solana_discovery_uses_restructured_market_section_order():
    html = render_solana_discovery_page()

    ordered_markers = (
        "TOTAL DEX VOLUME · 24H · SOLANA",
        "LIVE SIGNALS",
        '<div class="dex-section-label"><span>MARKET VIEWS</span>',
        'id="dex-market-panel-discovery"',
        '<div class="dex-section-label"><span>MARKET INTELLIGENCE</span>',
        "Experimental discovery · evidence synthesis only",
    )
    positions = [html.index(marker) for marker in ordered_markers]

    assert positions == sorted(positions)


def test_solana_discovery_market_tabs_have_exact_order_and_discovery_default():
    html = render_solana_discovery_page()

    ordered_tabs = (
        'data-market-tab="trending">Trending</button>',
        'data-market-tab="top-traded">Top Traded</button>',
        'data-market-tab="organic">Organic</button>',
        'data-market-tab="discovery">Discovery</button>',
        'data-market-tab="recent">Recent</button>',
    )
    positions = [html.index(marker) for marker in ordered_tabs]

    assert positions == sorted(positions)
    assert 'id="dex-market-tab-discovery" class="dex-market-tab" type="button" role="tab" aria-selected="true"' in html
    assert 'id="dex-market-panel-discovery" class="dex-market-panel dex-token-list" role="tabpanel"' in html
    assert "<h2>Token List</h2>" not in html
    assert "fetch(" not in html
    assert 'event.key === "ArrowRight"' in html
    assert 'event.key === "ArrowLeft"' in html


def test_solana_discovery_can_render_trending_as_initial_market_tab():
    html = render_solana_discovery_page(initial_market_tab="trending")

    assert 'id="dex-market-tab-trending" class="dex-market-tab" type="button" role="tab" aria-selected="true"' in html
    assert 'id="dex-market-tab-discovery" class="dex-market-tab" type="button" role="tab" aria-selected="false"' in html
    assert 'data-market-panel="trending">' in html
    assert 'data-market-panel="discovery" hidden>' in html


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

    assert "3271</strong>\n            <span>ACTIVE PAIRS" in html
    assert "Qualified Now" not in html
    assert '<form class="terminal-search"' not in html
    assert "Collector telemetry is connected; publication remains disabled." in html


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

    assert "Qualified Now" not in html
    assert "Example token" in html and "EX / SOL" in html
    assert "$12.00K" in html and "$4.50K" in html
    assert "data-token-address=\"token-address\"" in html
    assert 'class="sort-note"' in html
    assert 'class="dex-discovery-head"' in html
    assert 'class="dex-discovery-row candidate-row-v32"' in html
    assert "Page 1 of 1" in html
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
    assert "Volume 24h" in html
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

    assert 'class="dex-discovery-head"' in html
    assert "Observation" in html
    assert "Open Analysis &rarr;" in html
    assert "Previously qualified" in html
    assert "Â· exact pool" not in html

def test_solana_discovery_current_feed_keeps_observation_and_terminal_fonts():
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

    assert 'class="why-dot"' in html
    assert "Previously qualified" in html
    assert 'data-market-tab="trending">Trending</button>' in html
    assert 'data-market-tab="top-traded">Top Traded</button>' in html
    assert "MARKET INTELLIGENCE" in html
    assert 'font-family:Inter,"Segoe UI Variable Text"' in html


def test_solana_discovery_v29a_has_pagination_and_observed_network_facts():
    html = render_solana_discovery_page({
        "connected": True, "fresh": True, "qualified_candidates": 2,
        "qualified_total": 2, "recent_total": 5, "archive_total": 61,
        "view": "archive", "page": 3, "page_count": 3, "page_size": 25,
        "observed_volume_24h_usd": 12_345, "observed_txns_24h": 99,
        "observed_dex_ids": ["pumpswap", "raydium"],
        "candidates": [{
            "name": "Archived token", "symbol": "ARC", "quote_symbol": "SOL",
            "token_address": "archived-token", "pair_address": "archived-pool",
            "dex_id": "raydium", "price_usd": 0.25, "liquidity_usd": 12000,
            "volume_24h_usd": 4500, "pair_age": "3h",
        }],
    })
    assert "Qualified Now" not in html
    assert "Recent Discoveries" not in html
    assert "Full Archive" not in html
    assert '<form class="terminal-search"' not in html
    assert "Sorted by: Last qualified" in html
    assert "Page 3 of 3" in html
    assert "Archive Context" not in html


def test_solana_discovery_v291_explains_zero_qualification_without_broken_link():
    html = render_solana_discovery_page({
        "connected": True, "fresh": True, "qualified_candidates": 0,
        "qualified_total": 0, "recent_total": 71, "archive_total": 202,
        "view": "qualified", "page": 1, "page_count": 1, "page_size": 25,
        "observed_volume_24h_usd": 0, "observed_txns_24h": 0,
        "observed_dex_ids": [], "candidates": [],
    })
    assert "No qualified SOL pairs right now." in html
    assert "Tokens appear here only after identity, liquidity, activity and freshness checks pass." in html
    assert "View Recent Discoveries" not in html
    assert "Open Full Archive" not in html
    assert "preparing its first validated feed" not in html
    assert "#qualification-rules" not in html
    assert "Qualified Now" not in html
    assert "Recent Discoveries" not in html
    assert "Full Archive" not in html
    assert 'class="sort-note"' not in html
    assert 'class="feed-columns-v33"' not in html
    assert 'class="pagination"' not in html


@pytest.mark.parametrize("view", ("rolling", "qualified", "recent", "archive"))
def test_solana_discovery_keeps_server_view_context_without_legacy_navigation(view):
    html = render_solana_discovery_page({
        "view": view,
        "page": 1,
        "page_count": 1,
        "candidates": [],
    })

    assert '<form class="terminal-search"' not in html
    assert "Qualified Now" not in html
    assert "Recent Discoveries" not in html
    assert "Full Archive" not in html
    assert 'class="feed-tabs"' not in html
    assert 'class="feed-columns-v33"' not in html
    assert 'class="pagination"' not in html


def test_solana_discovery_v292_keeps_server_search_result_without_search_controls():
    html = render_solana_discovery_page({
        "connected": True, "fresh": True, "view": "archive", "page": 2,
        "page_count": 4, "page_size": 25, "view_total": 76,
        "qualified_total": 2, "recent_total": 10, "archive_total": 202,
        "search_query": "BER mint", "search_counts": {"qualified": 1, "recent": 3, "archive": 76},
        "candidates": [],
    })
    assert '<form class="terminal-search"' not in html
    assert 'aria-label="Search the discovery archive"' not in html
    assert "Sorted by: Last qualified" not in html
    assert "76 matching observations" not in html
    assert "view=archive&page=3&q=BER%20mint" not in html
    assert "view=recent" not in html
    assert "No matching token found." in html
    assert "Try another name, symbol, contract, pair address or DEX." in html
    assert "Clear search" in html


def test_solana_discovery_rolling_empty_state_explains_retention_window():
    html = render_solana_discovery_page({
        "view": "rolling",
        "page": 1,
        "page_count": 1,
        "candidates": [],
    })

    assert "No tokens qualified in the last 24 hours." in html
    assert (
        "Tokens remain visible here for 24 hours after their latest "
        "successful qualification."
    ) in html


def test_solana_discovery_v03e_is_responsive_and_accessible():
    html = render_solana_discovery_page()

    assert "/* TW-UI-03E — Responsive and accessibility hardening. */" in html
    assert "--faint:#718096" in html
    assert (
        'role="tablist" aria-label="Solana market categories" '
        'aria-orientation="horizontal"'
    ) in html
    assert '<nav class="discovery-segments-v1"' not in html
    assert '<form class="terminal-search"' not in html
    assert 'aria-label="Solana discovery products" role="tablist"' not in html
    assert 'href="/discovery/solana" role="tab"' not in html
    assert 'class="dex-empty-icon" aria-hidden="true">↗</span>' in html
    assert 'class="dex-empty-icon" aria-hidden="true">◇</span>' in html
    assert "/* DISCOVERY-UI-DEBT-01 — align Discovery with the current market-feed table. */" in html
    assert ".dex-volume-substat span{font-size:9px!important}" in html
    assert "@media(prefers-reduced-motion:reduce)" in html


def test_discovery_ui_debt_cleanup_matches_current_market_table_without_removed_chrome():
    html = render_solana_discovery_page({
        "connected": True,
        "fresh": True,
        "view": "qualified",
        "page": 1,
        "page_count": 1,
        "candidates": [{
            "name": "Example token",
            "symbol": "EX",
            "quote_symbol": "SOL",
            "token_address": "token-address",
            "dex_id": "raydium",
            "price_usd": 0.25,
            "change_24h": 12.5,
            "liquidity_usd": 12000,
            "volume_24h_usd": 45000,
            "pair_age": "2h",
            "currently_qualified": True,
        }],
    })

    assert "SOLANA DISCOVERY" not in html
    assert "<h2>Token List</h2>" not in html
    assert "Persistent, server-paginated observations." not in html
    assert "New Discoveries" not in html
    assert "Established Solana" not in html
    assert '<form class="terminal-search"' not in html
    assert 'class="dex-discovery-table"' in html
    assert 'class="dex-discovery-head"' in html
    assert 'class="dex-discovery-row candidate-row-v32"' in html
    assert 'class="dex-discovery-avatar"' in html
    assert "Currently qualified" in html
    assert "Open Analysis &rarr;" in html
    assert "Page 1 of 1" in html
