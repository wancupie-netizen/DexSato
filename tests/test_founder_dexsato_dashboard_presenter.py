"""Tests for the DexSato Founder V1 dashboard."""

from presentation.dexsato_dashboard_presenter import (
    build_intelligence_summary,
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
    assert "WATCH" in html
    assert "Decision Evidence" in html
    assert "Intelligence Summary" in html
    assert "View Decision" in html
    assert "/1.png" in html
    assert "Historical" not in html
    assert "decision-detail" in html


def test_should_render_dexsato_north_star_ui():
    html = render_dexsato_dashboard(
        SNAPSHOT,
        system_status=STATUS,
    )

    assert "<!doctype html>" in html
    assert "DEXSATO" in html
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
    assert '"Asia/Kuala_Lumpur"' in html
    assert "Search BTC, ETH, SUI..." in html
    assert "formatMYT" in html


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
