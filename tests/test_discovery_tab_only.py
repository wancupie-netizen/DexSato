from presentation.dexsato_solana_discovery_presenter import render_solana_discovery_page


def test_root_hides_only_discovery_tab_and_panel():
    html = render_solana_discovery_page(
        initial_market_tab="trending",
        show_discovery_tab=False,
    )
    assert 'data-market-tab="discovery"' not in html
    assert 'id="dex-market-panel-discovery"' not in html
    for tab in ("trending", "top-traded", "organic", "recent"):
        assert f'data-market-tab="{tab}"' in html
        assert f'id="dex-market-panel-{tab}"' in html


def test_legacy_discovery_render_still_has_its_tab_and_panel():
    html = render_solana_discovery_page()
    assert 'data-market-tab="discovery"' in html
    assert 'id="dex-market-panel-discovery"' in html
