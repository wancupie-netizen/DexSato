from presentation.dexsato_user_dashboard_presenter import render_user_dashboard


SNAPSHOT = {
    "generated_at": "2026-08-22T08:00:00+00:00",
    "total_coins": 3,
    "available_coins": 3,
    "coins": [
        {"token": "BTC", "pair": "BTC/USDT", "available": True,
         "decision": "ALERT", "confidence": "HIGH", "price": 70000,
         "liquidity": 1000000, "reasons": ["strong_liquidity"]},
        {"token": "ETH", "pair": "ETH/USDC", "available": True,
         "decision": "REVIEW", "confidence": "MEDIUM", "price": 2500,
         "liquidity": 800000, "reasons": ["weak_breakout"]},
        {"token": "XAU", "pair": "XAU/USD", "available": True,
         "decision": "REFERENCE", "confidence": "REFERENCE", "price": 4500,
         "reference_evidence": ["above_open"], "summary": "Reference market."},
    ],
}


def test_user_dashboard_focuses_on_market_evidence_not_operations():
    html = render_user_dashboard(
        SNAPSHOT,
        system_status={"snapshot": {"status": "FRESH"}},
    )

    assert "See what changed, what supports it, and what must happen next." in html
    assert "Market Decisions" in html
    assert "Needs attention" in html
    assert "How to read DexSato" in html
    assert "BTC/USDT" in html and "ETH/USDC" in html and "XAU/USD" in html
    assert "System Health" not in html
    assert "Provider Operations" not in html
    assert "Scheduler" not in html
    assert "Telegram" not in html
    assert "/admin/system" not in html


def test_user_dashboard_filters_attention_and_supports_mobile_layout():
    html = render_user_dashboard(SNAPSHOT, system_status={})

    assert 'data-filter="attention"' in html
    assert 'selected==="attention"?["alert","watch"]' in html
    assert 'id="show-attention"' in html
    assert 'scrollIntoView({behavior:"smooth",block:"start"})' in html
    assert "@media(max-width:780px)" in html
    assert "@media(max-width:430px)" in html


def test_user_dashboard_discloses_freshness_and_policy():
    html = render_user_dashboard(
        SNAPSHOT,
        system_status={"snapshot": {"status": "AGING"}},
    )

    assert "Aging" in html
    assert 'data-generated-at="2026-08-22T08:00:00+00:00"' in html
    assert "Evidence synthesis only · not financial advice." in html


def test_user_dashboard_uses_accessible_theme_icons():
    html = render_user_dashboard(SNAPSHOT, system_status={})

    assert 'data-theme-option="current"' in html
    assert 'aria-label="Use current dark theme"' in html
    assert 'aria-label="Use plain white theme"' in html
    assert "🌙" in html and "☀️" in html
    assert 'button.setAttribute("aria-pressed",String(active))' in html


def test_user_dashboard_mobile_polish_prevents_clipping_and_improves_readability():
    html = render_user_dashboard(SNAPSHOT, system_status={})

    assert "overflow-x:hidden" in html
    assert "grid-template-columns:64px minmax(0,1fr)" in html
    assert "contain:inline-size" in html
    assert "@media(max-width:520px)" in html
    assert ".filters button:last-child" in html
    assert "grid-column:1/-1" in html
    assert "width:calc(100% - 34px)" in html
    assert ".teaser-headline{font-size:16px" in html
    assert ".topbar{flex-direction:row;align-items:center}" in html
    assert ".top-actions{width:auto;margin-left:auto;justify-content:flex-end}" in html
