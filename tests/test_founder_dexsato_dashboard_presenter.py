"""Tests for the DexSato Founder V1 dashboard."""

from copy import deepcopy

from presentation.dexsato_dashboard_presenter import (
    build_intelligence_summary,
    format_compact_usd,
    format_usd,
    render_decision_card,
    render_dexsato_dashboard,
    render_market_detail_page,
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
            "volume_24h": 16594948.71,
            "market_cap": 1250000000000,
            "price_change_24h": 2.45,
            "chain": "bsc",
            "source": "DexScreener",
            "scanned_at": "2026-07-30T13:30:00+00:00",
            "trading_venues_status": "AVAILABLE",
            "trading_venues": [
                {
                    "name": "PancakeSwap",
                    "type": "DEX",
                    "pair": "BTC/USDT",
                    "volume_24h": 12000000,
                    "liquidity": 15000000,
                    "url": "https://dexscreener.com/bsc/0xpool",
                }
            ],
            "available": True,
            "decision": "WATCH",
            "confidence": "MEDIUM",
            "historical_success": 66.67,
            "reasons": ["MOMENTUM_STRENGTHENED"],
            "summary": "BTC remains under observation.",
            "technical_evidence_status": "AVAILABLE",
            "technical_evidence": {
                "status": "AVAILABLE",
                "timeframe": "4H",
                "source": "GeckoTerminal",
                "candle_closed_at": "2026-07-30T12:00:00+00:00",
                "metrics": {
                    "rsi_14": {
                        "value": 56.8,
                        "previous": 43.2,
                        "state": "NEUTRAL",
                        "direction": "RISING",
                    },
                    "ema_50": {"price_distance_pct": 1.8},
                    "ema_200": {"price_distance_pct": -2.4},
                    "relative_volume_20": {"value": 1.7},
                    "market_structure": {
                        "state": "HIGHER_HIGH_HIGHER_LOW",
                    },
                },
                "outlook": {
                    "bias": "BULLISH_DEVELOPING",
                    "summary": (
                        "Bullish 4H evidence is developing: 3/4 "
                        "directional checks are positive."
                    ),
                    "confirmation": [
                        {
                            "label": "Price holds above EMA50",
                            "status": "MET",
                            "actual": "+1.80%",
                            "requirement": "4H close above EMA50 (> 0.00%)",
                        },
                        {
                            "label": "Volume confirms participation",
                            "status": "PENDING",
                            "actual": "1.20×",
                            "requirement": "Relative volume at least 1.50×",
                        },
                    ],
                    "invalidation": [
                        {
                            "label": "4H close falls below EMA50",
                            "status": "CLEAR",
                            "actual": "+1.80%",
                            "requirement": "Triggered below 0.00%",
                        }
                    ],
                    "policy": "READ_ONLY_TECHNICAL_CONTEXT",
                },
            },
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
    assert "market-title-button" in html
    assert 'href="/market/btc"' in html
    assert "market-detail-template" not in html
    assert "data-open-market" not in html


def test_should_render_dedicated_market_detail_page():
    html = render_market_detail_page(
        SNAPSHOT["coins"][0],
        generated_at=SNAPSHOT["generated_at"],
    )

    assert "BTC/USDT Market Workspace" in html
    assert "24h Volume" in html
    assert "$16.59M" in html
    assert "+2.45%" in html
    assert "On-chain Market Cap" in html
    assert "BSC" in html
    assert "PancakeSwap" in html
    assert "ranked by 24h volume" in html
    assert "Technical Evidence · 4H" in html
    assert "56.80" in html
    assert "previously 43.20" in html
    assert "+1.80%" in html
    assert "-2.40%" in html
    assert "1.70×" in html
    assert "Higher High Higher Low" in html
    assert "GeckoTerminal" in html
    assert 'data-technical-at="2026-07-30T12:00:00+00:00"' in html
    assert "Current technical bias" in html
    assert "Bullish Developing" in html
    assert "Confirmation" in html
    assert "Invalidation" in html
    assert "Price holds above EMA50" in html
    assert "Actual: <strong>+1.80%</strong>" in html
    assert "Relative volume at least 1.50×" in html
    assert "does not override the DexSato decision" in html
    assert 'id="copy-summary"' in html
    assert 'href="/"' in html
    assert "market-drawer" not in html


def test_should_reject_untrusted_market_links():
    coin = {
        **SNAPSHOT["coins"][0],
        "trading_venues": [
            {
                "name": "Unsafe Venue",
                "type": "DEX",
                "pair": "BTC/USDT",
                "url": "javascript:alert(1)",
            }
        ],
    }

    html = render_market_detail_page(coin)

    assert "Unsafe Venue" in html
    assert "javascript:" not in html


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


def test_should_offer_current_and_plain_white_themes():
    html = render_dexsato_dashboard(
        SNAPSHOT,
        system_status=STATUS,
    )

    assert 'data-theme-option="current"' in html
    assert 'data-theme-option="plain"' in html
    assert "Plain White" in html
    assert 'html[data-theme="plain"]' in html
    assert 'localStorage.setItem("dexsato-theme",resolved)' in html
    assert 'localStorage.getItem("dexsato-theme")' in html
    assert 'data-theme-option="current" aria-pressed="true"' in html


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


def test_market_detail_renders_verified_fundamental_context():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["fundamental_context_status"] = "AVAILABLE"
    coin["fundamental_context"] = {
        "headline": "Official macro signals are mixed",
        "summary": "Context only; causality is not established.",
        "source": "U.S. Bureau of Labor Statistics",
        "source_url": "https://www.bls.gov/data/",
        "indicators": [{
            "label": "US CPI inflation (YoY)", "actual_display": "2.7%",
            "previous_display": "2.9%", "reference_period": "July 2026",
            "direction": "COOLING",
            "source_url": "https://data.bls.gov/timeseries/CUUR0000SA0",
        }],
    }
    html = render_market_detail_page(
        coin, generated_at="2026-08-19T00:00:00+00:00"
    )
    assert "Verified Fundamental Context" in html
    assert "Contextual · causality not established" in html
    assert "US CPI inflation (YoY)" in html
    assert "2.7%" in html and "2.9%" in html
    assert "U.S. Bureau of Labor Statistics" in html


def test_market_detail_renders_verified_official_catalysts():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["market_catalysts_status"] = "AVAILABLE"
    coin["market_catalysts"] = {"catalysts": [{
        "title": "Federal Reserve issues FOMC statement",
        "source": "Federal Reserve", "category": "MONETARY_POLICY",
        "published_at": "2026-08-18T18:00:00+00:00",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/a.htm",
    }]}
    html = render_market_detail_page(
        coin, generated_at="2026-08-19T00:00:00+00:00"
    )
    assert "Verified Market Catalysts" in html
    assert "Federal Reserve issues FOMC statement" in html
    assert "Contextual · not proof of cause" in html
    assert "DexSato does not infer sentiment or causality" in html


def test_market_detail_renders_trader_decision_brief():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["trader_decision_brief"] = {
        "status": "AVAILABLE", "state": "DOWNSIDE_EVIDENCE_DEVELOPING",
        "headline": "Downside evidence is developing",
        "summary": "Technical confirmation remains incomplete.",
        "next_action": "Wait for pending conditions before treating this as a setup.",
        "pending_confirmation": [{"label": "RSI confirms bearish momentum",
            "actual": "47.60", "requirement": "RSI below 45.00"}],
        "invalidation": [{"label": "4H close recovers above EMA50",
            "actual": "-0.28%", "requirement": "Triggered above 0.00%"}],
        "context_notes": [{"type": "MACRO", "text": "Official macro signals are mixed"}],
        "policy": "Evidence synthesis only; not a trade instruction.",
    }
    html = render_market_detail_page(coin, generated_at="2026-08-19T00:00:00+00:00")
    assert "Trader Decision Brief" in html
    assert "What this means now" in html
    assert "RSI confirms bearish momentum" in html
    assert "Context, not cause" in html
    assert "not a trade instruction" in html


def test_market_detail_renders_change_since_previous_scan():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["change_since_previous"] = {
        "status": "CHANGED",
        "headline": "4H bias changed from Mixed to Bearish Developing",
        "changes": [{"label": "RSI(14)", "previous": "54.39", "current": "47.60"}],
        "policy": "Observed snapshot differences only; no causal inference.",
    }
    html = render_market_detail_page(coin, generated_at="2026-08-19T00:00:00+00:00")
    assert "Since previous completed scan" in html
    assert "4H bias changed from Mixed to Bearish Developing" in html
    assert "54.39" in html and "47.60" in html
    assert "no causal inference" in html
