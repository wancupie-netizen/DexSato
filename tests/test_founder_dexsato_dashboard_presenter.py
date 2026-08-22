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
    assert "Evidence Snapshot · 4H" in html
    assert "Decision Brief" in html
    assert "Bullish Developing" in html
    assert "56.80" in html
    assert "Rising · previous 43.20" in html
    assert "1.70×" in html
    assert "Volume confirms participation" in html
    assert "Review Evidence &amp; Conditions" in html
    assert "/1.png" in html
    assert "Historical" not in html
    assert "decision-detail" in html
    assert "market-title-button" in html
    assert 'href="/market/btc"' in html
    assert "market-detail-template" not in html
    assert "data-open-market" not in html


def test_dashboard_contains_mobile_decision_card_overflow_guards():
    html = render_dexsato_dashboard(SNAPSHOT, system_status=STATUS)

    assert "@media(max-width:430px)" in html
    assert "grid-template-columns:minmax(0,1fr)" in html
    assert "overflow-wrap:anywhere" in html
    assert "white-space:normal" in html
    assert "max-width:calc(100vw - 24px)" in html
    assert "contain:inline-size" in html
    assert "decision-button-label" in html
    assert 'querySelectorAll("button.decision-button")' in html


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


def test_market_detail_renders_evidence_health_and_source_states():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["evidence_health"] = {
        "status": "PARTIAL",
        "summary": "Core evidence is fresh, but one contextual source is unavailable.",
        "checks": {
            "market_snapshot": {"label": "Market snapshot", "state": "FRESH"},
            "technical_4h": {"label": "Technical evidence · 4H", "state": "AGING"},
            "market_catalysts": {"label": "Official market catalysts", "state": "UNAVAILABLE"},
        },
    }

    html = render_market_detail_page(coin, generated_at=SNAPSHOT["generated_at"])

    assert "Evidence Health" in html
    assert "Data quality &amp; freshness" in html
    assert "Partial" in html
    assert "Technical evidence · 4H" in html
    assert "Aging" in html
    assert "Unavailable" in html


def test_stale_evidence_health_suppresses_current_technical_homepage_teaser():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["evidence_health"] = {
        "status": "STALE", "technical_usable": False,
        "summary": "A required evidence source is stale.",
    }

    html = render_decision_card(coin)

    assert "DATA QUALITY NOTICE" in html
    assert "Required evidence is stale" in html
    assert "Fresh scan required" in html
    assert "56.80" not in html


def test_market_detail_renders_decision_readiness_without_trade_claim():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["decision_readiness"] = {
        "status": "DEVELOPING",
        "headline": "The evidence case is still developing",
        "summary": "One of two confirmation conditions is met.",
        "confirmation": {"met": 1, "pending": 1, "total": 2},
        "supporting_conditions": ["Price holds above EMA50"],
        "pending_conditions": ["Volume confirms participation"],
        "conflicts": [],
    }

    html = render_market_detail_page(coin, generated_at=SNAPSHOT["generated_at"])

    assert "Decision Readiness" in html
    assert "Developing" in html
    assert "Supporting now" in html
    assert "Price holds above EMA50" in html
    assert "Still required" in html
    assert "Volume confirms participation" in html
    assert "not trade readiness or a trade instruction" in html


def test_market_detail_discloses_directional_conflict():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["decision_readiness"] = {
        "status": "CONFLICTED",
        "headline": "Engine and technical direction do not align",
        "summary": "Opposing directional evidence is present.",
        "confirmation": {"met": 1, "pending": 2, "total": 3},
        "supporting_conditions": ["Price structure"],
        "pending_conditions": ["RSI", "Volume"],
        "conflicts": ["Engine signals are bearish while 4H technical evidence is bullish."],
    }

    html = render_market_detail_page(coin, generated_at=SNAPSHOT["generated_at"])

    assert "Conflicted" in html
    assert "Conflict detected" in html
    assert "Engine signals are bearish" in html


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


def test_dashboard_renders_provider_operations_from_snapshot():
    snapshot = deepcopy(SNAPSHOT)
    snapshot["provider_health"] = {
        "status": "RECOVERED",
        "providers": [{
            "provider": "DexScreener exact pair", "status": "RECOVERED",
            "logical_requests": 5, "attempts": 6, "retries": 1, "failures": 0,
        }],
    }

    html = render_dexsato_dashboard(snapshot, system_status=STATUS)

    assert 'Provider APIs</span><b class="provider-overall-recovered">RECOVERED' in html
    assert "Provider Operations" in html
    assert "DexScreener exact pair" in html
    assert "5 requests · 1 retries · 0 failures" in html
    assert "provider-recovered" in html


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
    assert 'aria-label="Use current dark theme"' in html
    assert 'aria-label="Use plain white theme"' in html
    assert "🌙" in html and "☀️" in html
    assert 'html[data-theme="plain"]' in html
    assert 'localStorage.setItem("dexsato-theme",resolved)' in html
    assert 'localStorage.getItem("dexsato-theme")' in html
    assert 'aria-pressed="true"' in html


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


def test_market_detail_renders_recent_scan_trail():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["recent_scan_history"] = [{
        "recorded_at": "2026-08-19T04:00:00+00:00", "decision": "REVIEW",
        "confidence": "MEDIUM", "technical_bias": "BEARISH_DEVELOPING",
        "rsi_14": 47.6, "relative_volume": .78, "price": 64300,
    }, {
        "recorded_at": "2026-08-19T08:00:00+00:00", "decision": "ALERT",
        "confidence": "HIGH", "technical_bias": "BULLISH_DEVELOPING",
        "rsi_14": 56.2, "relative_volume": 1.6, "price": 65100,
    }]
    html = render_market_detail_page(coin, generated_at="2026-08-19T08:00:00+00:00")
    assert "Recent Scan Trail" in html
    assert "2 stored scans" in html
    assert "Bearish Developing" in html and "Bullish Developing" in html
    assert "RSI 56.20" in html and "Vol 1.60×" in html
    assert "maximum 12 stored" in html


def test_market_detail_renders_evidence_follow_through():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["evidence_follow_through"] = {
        "status": "AVAILABLE",
        "message": "Price follow-through after previously recorded directional evidence.",
        "policy": "Evidence follow-through only; not win rate, P&L or trade advice.",
        "evaluations": [{
            "horizon": "4H", "assessment": "SUPPORTIVE",
            "recorded_bias": "BEARISH_DEVELOPING",
            "anchor_at": "2026-08-19T00:00:00+00:00",
            "price_change_pct": -2.0,
        }],
    }
    html = render_market_detail_page(coin, generated_at="2026-08-19T04:00:00+00:00")
    assert "Evidence Follow-Through" in html
    assert "Supportive" in html
    assert "Bearish Developing" in html
    assert "-2.00%" in html
    assert "not win rate, P&amp;L or trade advice" in html


def test_market_detail_renders_exact_pool_live_quote_controls():
    html = render_market_detail_page(
        deepcopy(SNAPSHOT["coins"][0]),
        generated_at="2026-08-22T05:00:00+00:00",
    )

    assert "Live Price &amp; Market Chart" in html
    assert "data-live-price" in html
    assert "data-live-change" in html
    assert "data-live-quote-status" in html
    assert "/quote" in html
    assert "window.setInterval(loadLiveQuote,10000)" in html
    assert "window.setInterval(updateQuoteAge,1000)" in html
    assert 'second:"2-digit"' in html
    assert "quote-price-up" in html and "quote-price-down" in html
    assert "prefers-reduced-motion:reduce" in html
    assert "window.setInterval(()=>" in html and "60000" in html
    assert 'document.addEventListener("visibilitychange"' in html
    assert "EXACT_POOL_INFORMATIONAL_QUOTE" not in html
    assert "not a Jupiter execution quote or trade instruction" in html
