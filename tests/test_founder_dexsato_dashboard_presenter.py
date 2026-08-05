"""Tests for the DexSato Founder V1 dashboard."""

from presentation.dexsato_dashboard_presenter import (
    build_intelligence_summary,
    format_compact_usd,
    format_usd,
    render_decision_card,
    render_dexsato_dashboard,
)


SNAPSHOT = {
    "generated_at": "2026-07-30T13:32:45+00:00",
    "total_coins": 2,
    "available_coins": 2,
    "unavailable_coins": 0,
    "coins": [
        {
            "token": "BTC",
            "pair": "BTC/USDT",
            "price": "64202.82",
            "liquidity": 15149834.19,
            "available": True,
            "decision": "WATCH",
            "confidence": "MEDIUM",
            "historical_success": 66.67,
            "reasons": ["MOMENTUM_STRENGTHENED"],
            "summary": "BTC remains under observation.",
        },
        {
            "token": "SUI",
            "available": True,
            "decision": "ALERT",
            "confidence": "HIGH",
            "historical_success": 80,
            "reasons": ["MULTIPLE_SIGNALS_ALIGNED"],
            "summary": "Founder attention is required.",
        },
        {
            "token": "XAU",
            "pair": "XAU/USD",
            "price": "4073.39",
            "liquidity": None,
            "available": True,
            "decision": "REFERENCE",
            "confidence": "REFERENCE",
            "historical_success": None,
            "reasons": [],
            "reference_evidence": [
                "ABOVE_OPEN",
                "UPPER_RANGE",
                "DAILY_CHANGE_+0.5000%",
            ],
            "summary": (
                "XAU/USD is above the daily open and in the upper "
                "third of today's range. This is reference "
                "intelligence, not a trade signal."
            ),
        },
    ],
}


STATUS = {
    "overall_health": "HEALTHY",
    "snapshot": {"status": "FRESH"},
    "latest_run": {
        "generated_at": "2026-07-30T13:32:45+00:00",
        "telegram_status": "SENT",
        "change_summaries": ["SUI: REVIEW → ALERT"],
    },
    "tasks": [
        {
            "installed": True,
            "last_result_status": "SUCCESS",
        }
    ],
}


def test_should_render_real_decision_card():
    html = render_decision_card(SNAPSHOT["coins"][0])

    assert "BTC" in html
    assert "BTC/USDT" in html
    assert "$64,202.82" in html
    assert "Liquidity $15.15M" in html
    assert "WATCH" in html
    assert "Decision Evidence" in html
    assert "Intelligence Summary" in html
    assert "Risk Note" in html
    assert "View Decision" in html
    assert "/1.png" in html
    assert "Historical" not in html
    assert "decision-detail" in html


def test_should_render_gold_as_reference_market():
    html = render_decision_card(SNAPSHOT["coins"][2])

    assert "XAU/USD" in html
    assert "$4,073.39" in html
    assert "Liquidity Not available" in html
    assert "REFERENCE" in html
    assert "not a trade signal" in html
    assert "Above Open" in html
    assert "Upper Range" in html
    assert 'class="commodity-fallback">Au</span>' in html


def test_should_format_market_values():
    assert format_usd("1871.3") == "$1,871.30"
    assert format_usd("1.077") == "$1.0770"
    assert format_usd("0.6936") == "$0.6936"
    assert format_compact_usd(99221150.8) == "$99.22M"
    assert format_usd(None) == "Not available"


def test_should_render_dexsato_north_star_ui():
    html = render_dexsato_dashboard(
        SNAPSHOT,
        system_status=STATUS,
    )

    assert "<!doctype html>" in html
    assert 'src="/static/branding/dexsato-logo.png"' in html
    assert 'alt="DexSato"' in html
    assert 'href="/static/branding/favicon.png"' in html
    assert "brand-mark" not in html
    assert "Market Decision Intelligence" in html
    assert "Decision Timeline" in html
    assert "Market State" in html
    assert "SUI: REVIEW → ALERT" in html
    assert "Scheduler</span><b>HEALTHY" in html
    assert "Made for Sya ❤️" in html
    assert "99.8%" not in html


def test_should_keep_dashboard_search_and_filters():
    html = render_dexsato_dashboard(
        SNAPSHOT,
        system_status=STATUS,
    )

    assert 'id="token-search"' in html
    assert "function applyFilters()" in html
    assert 'data-filter="alert"' in html
    assert 'data-filter="unavailable"' in html
    assert 'data-filter="reference"' in html
    assert '"Asia/Kuala_Lumpur"' in html
    assert "Search BTC, ETH, SUI..." in html
    assert "formatMYT" in html


def test_should_use_canonical_snapshot_time_when_latest_run_is_older():
    stale_run_status = {
        **STATUS,
        "latest_run": {
            **STATUS["latest_run"],
            "generated_at": "2026-07-25T06:00:00+00:00",
        },
    }

    html = render_dexsato_dashboard(
        SNAPSHOT,
        system_status=stale_run_status,
    )

    assert (
        'data-generated-at="2026-07-30T13:32:45+00:00"'
        in html
    )
    assert 'data-generated-at="2026-07-25T06:00:00+00:00"' not in html


def test_should_build_grounded_intelligence_summary():
    summary = build_intelligence_summary(
        token="ETH",
        decision="ALERT",
        confidence="HIGH",
        reasons=[
            "EARLY_MOMENTUM",
            "STRONG_LIQUIDITY",
        ],
    )

    assert "requires immediate founder attention" in summary
    assert "Early Momentum" in summary
    assert "Strong Liquidity" in summary
    assert "Confidence is HIGH" in summary
