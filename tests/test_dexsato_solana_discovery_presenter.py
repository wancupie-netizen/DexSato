from presentation.dexsato_solana_discovery_presenter import (
    render_solana_discovery_page,
)


def test_solana_discovery_prototype_is_honest_and_read_only():
    html = render_solana_discovery_page()

    assert "Solana Discovery" in html
    assert "Evidence-led token discovery" in html
    assert "Discovery candidates are not connected yet." in html
    assert "No discovery tokens are available yet." in html
    assert "Read-only preview" in html
    assert "Jupiter execution · planned, not active" in html
    assert "No wallet connection, quote or trading capability" in html
    assert "will not hold your keys or funds" in html


def test_solana_discovery_has_search_filters_and_no_fake_candidates():
    html = render_solana_discovery_page()

    assert "Search token name, symbol, or contract address" in html
    assert "Newly active" in html
    assert "Volume rising" in html
    assert "Liquidity improving" in html
    assert "Higher risk" in html
    assert "Tokens observed</span><strong>—" in html
    assert "Qualified candidates</span><strong>—" in html
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

    assert "Collector telemetry is connected." in html
    assert "Tokens observed</span><strong>4742" in html
    assert "Pairs resolved</span><strong>3271" in html
    assert "Qualified candidates</span><strong>—" in html
    assert "5 min ago" in html
