from pathlib import Path

from presentation.dexsato_solana_discovery_token_presenter import render_solana_discovery_token_page


DETAIL = {
    "token_address": "TokenAddress123456789", "pair_address": "PoolAddress123456789",
    "symbol": "TEST", "name": "Test Token", "quote_symbol": "SOL",
    "dex_id": "raydium", "price_usd": .12, "change_24h": 4.5,
    "liquidity_usd": 7000, "volume_24h_usd": 3000, "market_cap": 120000,
    "pair_age": "2h", "quote_status": "LIVE", "quote_label": "Live exact-pool observation",
    "evidence": "Observed liquidity and activity.", "risk_label": "Security unavailable",
    "source_url": "https://dexscreener.com/solana/pool", "feed_updated_label": "4 min ago",
    "currently_qualified": True,
    "chart": [
        {"close": .10}, {"close": .11}, {"close": .105},
        {"close": .115}, {"close": .108}, {"close": .12},
    ],
}



# TOKEN_WORKSPACE_V251_CANDLESTICK_TEST_MIGRATION
def test_renders_exact_token_workspace_and_chart():
    candle = {
        "time": 1700000000,
        "open": 0.10,
        "high": 0.12,
        "low": 0.09,
        "close": 0.11,
        "volume": 100.0,
    }
    detail = {
        **DETAIL,
        "candlestick_timeframes": {
            "1m": [candle],
            "5m": [candle],
            "15m": [candle],
            "30m": [candle],
            "1H": [candle],
            "4H": [candle],
        },
    }

    html = render_solana_discovery_token_page(detail)

    assert "TEST / SOL" in html
    assert 'data-candlestick-panel' in html
    assert 'aria-label="Exact-pool interactive candlestick chart"' in html
    assert 'data-candle-timeframe="1m"' in html
    assert 'data-candle-timeframe="5m"' in html
    assert 'data-candle-timeframe="15m"' in html
    assert 'data-candle-timeframe="30m"' in html
    assert 'data-candle-timeframe="1H"' in html
    assert 'data-candle-timeframe="4H"' in html
    assert "Validated exact-pool data" not in html
    assert "4H Market Chart" not in html
    assert "Closed market intervals; not an executable quote." not in html
    assert "GeckoTerminal" not in html
    assert 'src="/static/branding/dexsato-logo.png"' in html
    assert 'data-copy-address="TokenAddress123456789"' in html

def test_renders_controlled_jupiter_swap_with_solana_badge_and_discloses_risk():
    html = render_solana_discovery_token_page(DETAIL)
    assert "Trade TEST" in html
    assert 'data-trade-side="buy" aria-pressed="true">Buy' in html
    assert 'data-trade-side="sell" aria-pressed="false">Sell' in html
    assert '<span class="trade-network-v04"><i aria-hidden="true"></i>Solana</span>' in html
    assert "NON-CUSTODIAL" not in html
    assert "Connect wallet" in html
    assert "Get buy quote" in html
    assert "Before you continue" in html
    assert "I reviewed the quote and risks." in html
    assert "Review buy" in html
    assert 'data-confirmation-summary hidden' in html
    assert 'data-swap-risk-ack' in html
    assert 'data-execute-swap disabled' in html
    assert 'data-token-symbol="TEST"' in html
    assert 'src="/static/js/dexsato_solana_discovery_swap.js?v=tw-dex-04" defer' in html
    assert "Fees are shown in the quote and order review before wallet approval." in html
    assert "Pool verification is not token verification" in html
    assert "never holds your funds" in html
    assert "You approve every transaction in your wallet" in html
    assert html.index("Risk context") < html.index("Current qualification")
    assert html.index("Trade TEST") < html.index("Risk context")
    assert 'class="card jupiter jupiter-v27 trade-v04" data-jupiter-sandbox' in html


def test_archive_observation_keeps_user_directed_swap_controls_with_context():
    html = render_solana_discovery_token_page({**DETAIL, "currently_qualified": False})

    assert "Trade TEST" in html
    assert '<span class="trade-network-v04"><i aria-hidden="true"></i>Solana</span>' in html
    assert "Previously discovered" not in html
    assert "This token was previously discovered by DexSato." not in html
    assert "Check the latest market data and quote before you continue." not in html
    assert "Not evaluated in this scan" in html
    assert "No current scan assessment was recorded for this archived observation." in html
    assert "This qualification status is analysis context, not a trading restriction." not in html
    assert '<section class="card jupiter jupiter-v27 trade-v04" data-jupiter-sandbox' in html
    assert "Connect wallet" in html
    assert "Get buy quote" in html
    assert "Review buy" in html


def test_renders_recorded_current_qualification_reason_and_labels_history():
    html = render_solana_discovery_token_page({
        **DETAIL,
        "currently_qualified": False,
        "last_qualified_at": "2026-08-27T23:48:00+00:00",
        "current_qualification": {
            "evaluated": True,
            "qualified": False,
            "code": "liquidity_below_threshold",
            "title": "Liquidity below qualification threshold",
            "message": "Observed liquidity $4,900.00 is below the required $5,000.00.",
            "scan_at": "2026-08-27T23:50:00+00:00",
        },
    })

    assert "Current qualification" in html
    assert "Liquidity below qualification threshold" in html
    assert "Observed liquidity $4,900.00 is below the required $5,000.00." in html
    assert "Last confirmed checks" in html
    assert "Last qualified:" in html
    assert "Current scan:" in html
    assert "2026-08-27T23:48:00+00:00" not in html
    assert "2026-08-27T23:50:00+00:00" not in html
    assert "Collector updated Unknown" not in html
    assert "Checks passed for this feed" not in html



def test_chart_fails_safely_when_unavailable():
    html = render_solana_discovery_token_page({
        **DETAIL,
        "chart": [],
        "candlestick_timeframes": {
            "1m": [],
            "5m": [],
            "15m": [],
            "30m": [],
            "1H": [],
            "4H": [],
        },
    })

    assert 'data-candlestick-panel' in html
    assert "Market candles unavailable for this timeframe." in html
    assert "Insufficient chart history" not in html
    assert "Only 0 closed 4H candles available" not in html


# TOKEN_WORKSPACE_V26A_THREE_COLUMN_SHELL
def test_token_workspace_v26a_renders_three_column_shell_without_fake_timeline():
    feed = {
        "connected": True,
        "candidates": [
            {**DETAIL, "token_address": "TokenAddress123456789"},
            {
                "token_address": "SecondToken987654321",
                "symbol": "NEXT",
                "quote_symbol": "SOL",
                "price_usd": 0.0042,
                "change_24h": -2.5,
            },
        ],
    }

    html = render_solana_discovery_token_page(DETAIL, feed=feed)

    assert "TOKEN_WORKSPACE_V26A_THREE_COLUMN_SHELL" in html
    assert 'class="token-workspace-v26"' in html
    assert 'class="workspace-rail-v26 workspace-left-v26"' in html
    assert 'class="workspace-main-v26"' in html
    assert 'class="workspace-rail-v26 workspace-right-v26"' in html
    assert html.index("Token Observation") < html.index("Coin List")
    assert html.index("Coin List") < html.index("TEST / SOL")
    assert html.index("Trade TEST") < html.index("Market Snapshot")
    assert "Coin Timeline" not in html
    assert "Recent Events" not in html
    assert "Pool detected" not in html
    assert "Route availability is not a safety guarantee." in html


def test_token_observation_renders_only_requested_factual_fields():
    html = render_solana_discovery_token_page(DETAIL, feed=None)

    assert 'data-token-observation' in html
    for label in ("Mint authority", "Freeze authority", "Metadata", "Sell route verified", "Liquidity", "24h change"):
        assert label in html


def test_token_workspace_v26a2_keeps_right_rail_cards_in_one_static_flow():
    html = render_solana_discovery_token_page(DETAIL, feed=None)

    assert ".workspace-right-v26{position:static;max-height:none;overflow:visible" in html
    assert 'html[data-theme="intel"] .workspace-right-v26 .decision-side-v2{position:static!important;top:auto!important}' in html
    assert ".workspace-right-v26 .market-snapshot-v26{position:static" in html
    assert "overscroll-behavior:auto" in html


def test_token_observation_keeps_coin_navigation_below_observation():
    html = render_solana_discovery_token_page(DETAIL, feed={"candidates": [DETAIL]})
    assert '<section class="workspace-rail-card coin-list"' in html
    assert '<a class="coin-list-row active"' in html
    assert html.index('data-token-observation') < html.index('data-coin-list')


def test_token_workspace_v26a4_removes_competing_vertical_scrollbars():
    html = render_solana_discovery_token_page(DETAIL, feed=None)

    assert ".workspace-right-v26{position:static;max-height:none;overflow:visible" in html
    assert ".transactions-table-wrap{max-height:none;overflow-x:auto;overflow-y:visible" in html
    assert "html{scrollbar-width:none}html::-webkit-scrollbar{display:none}" in html

def test_swap_client_requires_explicit_wallet_signing_and_preserves_same_origin_api_keys():
    script = (
        Path(__file__).resolve().parents[1]
        / "static" / "js" / "dexsato_solana_discovery_swap.js"
    ).read_text(encoding="utf-8")

    assert "walletProvider.signTransaction(unsigned)" in script
    assert "VersionedTransaction.deserialize" in script
    assert 'apiBase + "/jupiter-order"' in script
    assert 'apiBase + "/jupiter-execute"' in script
    assert "risk_acknowledged: acknowledgement.checked" in script
    assert 'sellRouteStatus.textContent = "Verified · just now"' in script
    assert "Retry signed transaction" in script
    assert "credentials: \"same-origin\"" in script
    assert "x-api-key" not in script
    assert "privateKey" not in script and "seedPhrase" not in script


def test_trade_percentage_controls_use_authoritative_raw_wallet_balances():
    html = render_solana_discovery_token_page(DETAIL, feed=None)
    script = (
        Path(__file__).resolve().parents[1]
        / "static" / "js" / "dexsato_solana_discovery_swap.js"
    ).read_text(encoding="utf-8")

    for percent in (25, 50, 75, 100):
        assert f'data-amount-percent="{percent}"' in html
    assert 'data-buy-value="0.1"' not in html
    assert 'apiBase + "/wallet-balance?wallet_address="' in script
    assert "BigInt(raw) * BigInt(percent)" in script
    assert 'button.textContent = side === "buy" ? "MAX" : "100%"' in script
    assert "walletBalance.sell_percentage_ready === true" in script
    assert "Number(first)" not in script and "Number(second)" not in script


def test_jupiter_v27_renders_readable_quote_preview_fields():
    script = (
        Path(__file__).resolve().parents[1]
        / "static" / "js" / "dexsato_solana_discovery_swap.js"
    ).read_text(encoding="utf-8")

    assert '"Sell" : "Buy") + " quote preview"' in script
    assert '"Expected receive"' in script
    assert '"Minimum receive"' in script
    assert '"Price impact"' in script
    assert '"Slippage"' in script
    assert '"Estimated network fee", "Shown by wallet"' in script
    assert 'fresh.textContent = "● Updated just now"' in script
    assert "payload.minimum_received_raw" in script
    assert "payload.minimum_received_ui" in script
    assert '"Output decimals"' in script
    assert "payload.output_decimals_source" in script
    assert "payload.slippage_bps" in script


def test_jupiter_v27_requires_confirmation_summary_before_wallet_signing():
    script = (
        Path(__file__).resolve().parents[1]
        / "static" / "js" / "dexsato_solana_discovery_swap.js"
    ).read_text(encoding="utf-8")

    review = script.index("if (!confirmationOpen)")
    confirmation = script.index("renderConfirmation(currentQuote);", review)
    early_return = script.index("return;", confirmation)
    signing = script.index("walletProvider.signTransaction(unsigned)")
    assert review < confirmation < early_return < signing
    assert 'heading.textContent = "Confirmation summary"' in script
    assert 'swapButton.textContent = "Confirm " + payload.side + " in wallet"' in script
    assert 'swapButton.textContent = "Review " + side' in script


def test_tw_dex_04_uses_approved_trade_panel_and_marks_connected_wallet():
    html = render_solana_discovery_token_page(DETAIL)
    script = (
        Path(__file__).resolve().parents[1]
        / "static" / "js" / "dexsato_solana_discovery_swap.js"
    ).read_text(encoding="utf-8")

    assert "TOKEN_WORKSPACE_V271_JUPITER_COMPACT_HEADER" in html
    assert "TW-DEX-04 — two-way Jupiter execution panel" in html
    assert "TW-DEX-04A — rounded trade-card polish" in html
    assert 'class="trade-switch-v04"' in html
    assert 'class="trade-amount-v04"' in html
    assert 'class="trade-receive-v04"' in html
    assert 'data-route-summary' in html
    assert '.trade-v04[data-side="sell"]{--trade-accent:var(--red)}' in html
    assert "border-radius:11px!important;overflow:hidden" in html
    assert ".wallet-state.connected{color:var(--green)}" in html
    assert 'walletState.classList.add("connected")' in script
    assert 'walletAddress.slice(0, 4) + "…"' in script


def test_jupiter_v272_resets_confirmation_and_focuses_amount_after_balance_failure():
    html = render_solana_discovery_token_page(DETAIL)
    script = (
        Path(__file__).resolve().parents[1]
        / "static" / "js" / "dexsato_solana_discovery_swap.js"
    ).read_text(encoding="utf-8")

    assert "TOKEN_WORKSPACE_V272_QUOTE_FAILURE_STATE" in html
    assert 'data-swap-input-error hidden role="alert"' in html
    assert 'const insufficientBalance = /insufficient (sol|token) balance/i.test(message);' in script
    assert "clearConfirmation();" in script
    assert "acknowledgement.checked = false;" in script
    assert "setInputError(message);" in script
    assert "amount.focus();" in script
    assert "amount.select();" in script


def test_jupiter_v272_formats_raw_quote_values_without_false_precision():
    script = (
        Path(__file__).resolve().parents[1]
        / "static" / "js" / "dexsato_solana_discovery_swap.js"
    ).read_text(encoding="utf-8")

    assert 'notation: "compact", maximumFractionDigits: 2' in script
    assert 'maximumFractionDigits: 4' in script
    assert 'minimum > 0' in script
    assert 'bps > 0' in script
    assert 'return "Unavailable";' in script
    assert 'receiveAmount.textContent = compactOutput(payload);' in script



def test_chart_does_not_imply_a_trend_from_two_candles():
    candles = [
        {
            "time": 1700000000,
            "open": 0.10,
            "high": 0.13,
            "low": 0.09,
            "close": 0.12,
            "volume": 100.0,
        },
        {
            "time": 1700014400,
            "open": 0.12,
            "high": 0.125,
            "low": 0.07,
            "close": 0.08,
            "volume": 120.0,
        },
    ]
    html = render_solana_discovery_token_page({
        **DETAIL,
        "chart": candles,
        "candlestick_timeframes": {
            "1m": [],
            "5m": [],
            "15m": [],
            "30m": [],
            "1H": [],
            "4H": candles,
        },
    })

    assert 'data-candlestick-panel' in html
    assert '"4H":[{"time":1700000000' in html
    assert "Only 2 closed 4H candles available" not in html
    assert "At least 6 are required" not in html
    assert "<polyline" not in html


def test_chart_sanitizer_keeps_observed_flat_candle_without_current_price_repair():
    html = render_solana_discovery_token_page({
        **DETAIL,
        "price_usd": 99.0,
    })

    assert "TW-DEX-03J.1 — Observed Candle Sanitizer" in html
    assert "(hasCurrentObservedPrice?currentObservedPrice:null)" not in html
    assert "if([open,high,low,close].some(value=>value===null)) return null;" in html
    assert "Math.abs(high-low)<=epsilon" in html


def test_chart_sanitizer_deduplicates_timestamp_after_validating_ohlc():
    html = render_solana_discovery_token_page(DETAIL)

    assert "if(!Number.isFinite(time)||seen.has(time)) return;" in html
    assert "const clean=sanitizeOhlc(row);" in html
    assert "if(!clean) return;" in html
    assert "seen.add(time);" in html
    assert html.index("if(!clean) return;") < html.index("seen.add(time);")

def test_token_workspace_supports_market_intelligence_theme():
    html = render_solana_discovery_token_page({
        "symbol": "EX",
        "name": "Example",
        "quote_symbol": "SOL",
        "token_address": "token-address",
        "pair_address": "pair-address",
        "dex_id": "pumpswap",
        "quote_status": "LIVE",
        "quote_label": "Live exact-pool observation",
        "chart": [],
    })

    assert 'data-theme-option="current"' in html
    assert 'data-theme-option="intel"' in html
    assert 'data-theme-option="plain"' in html
    assert 'html[data-theme="intel"]' in html


def test_v283_evidence_strip_has_structural_css_in_every_theme():
    html = render_solana_discovery_token_page(DETAIL)

    assert "TOKEN_WORKSPACE_V283_THEME_PARITY" in html
    assert ".dexsato-evidence-strip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr))" in html
    assert ".dexsato-evidence-label{display:block;margin-bottom:5px" in html
    assert ".dexsato-evidence-value{display:flex;align-items:center;gap:7px" in html
    assert ".dexsato-evidence-dot{width:7px;height:7px" in html
    assert 'html[data-theme="plain"]{color-scheme:light;--bg:#f5f7fa;--panel:#fff;--panel2:#eef3f8;--line:#c8d3df' in html
    assert 'localStorage.getItem("dexsato-theme")' in html


def test_token_workspace_v2_decision_layout_is_ui_only():
    html = render_solana_discovery_token_page({
        "symbol": "EX", "name": "Example", "quote_symbol": "SOL",
        "token_address": "token-address", "pair_address": "pair-address",
        "dex_id": "pumpswap", "quote_status": "LIVE",
        "quote_label": "Live exact-pool observation", "chart": [],
        "currently_qualified": True,
    })
    assert "Token Workspace v2 Decision Layout" in html
    assert "dexsato-evidence-strip" in html
    assert "decision-grid-v2" in html
    assert "Not independently verified" in html
    assert "Trade EX" in html
    assert "Get buy quote" in html


def test_token_header_v22_uses_trader_standard_timeframes():
    detail = {
        "symbol": "TEST",
        "name": "Test Token",
        "quote_symbol": "SOL",
        "token_address": "token-address",
        "pair_address": "pair-address",
        "dex_id": "pumpswap",
        "quote_status": "LIVE",
        "quote_label": "Live exact-pool observation",
        "chart": [],
        "change_1m": 1.25,
        "change_5m": -2.5,
        "change_15m": 3.75,
        "change_30m": None,
        "change_1h": 8.0,
        "change_4h": None,
    }

    html = render_solana_discovery_token_page(detail)

    for timeframe in ("1m", "5m", "15m", "30m", "1H", "4H"):
        assert f'data-timeframe="{timeframe}"' in html

    assert "+1.25%" in html
    assert "-2.50%" in html
    assert "+3.75%" in html
    assert "+8.00%" in html
    assert "trader-tf-value unavailable" in html


def test_token_header_v22_does_not_fabricate_missing_timeframe_history():
    detail = {
        "symbol": "NEW",
        "name": "New Token",
        "quote_symbol": "SOL",
        "token_address": "token-address",
        "pair_address": "pair-address",
        "dex_id": "pumpswap",
        "quote_status": "LIVE",
        "quote_label": "Live exact-pool observation",
        "chart": [],
    }

    html = render_solana_discovery_token_page(detail)

    assert html.count('trader-tf-value unavailable">&#8212;</strong>') == 6

def test_token_workspace_v24_renders_unified_token_card():
    detail = dict(DETAIL)
    detail.update({
        "symbol": "ALTF",
        "quote_symbol": "USDC",
        "name": "American Liberty Trust Fund",
        "price_usd": 0.00321,
        "change_24h": 18.4,
        "dex_id": "pumpswap",
        "age_label": "2h",
        "quote_status": "LIVE",
        "token_image_url": "https://cdn.example.com/token.png",
        "website_url": "https://example.com",
        "telegram_url": "https://t.me/example",
        "twitter_url": "https://x.com/example",
        "change_1m": 0.06,
        "change_5m": 0.10,
        "change_15m": 0.13,
        "change_30m": 0.12,
        "change_1h": 0.31,
        "change_4h": 0.55,
    })

    html = render_solana_discovery_token_page(detail)

    assert 'class="token-overview-card"' in html
    assert "ALTF / USDC" in html
    assert "$0.0032" in html
    assert "+18.40%" in html
    assert ">LIVE<" in html
    assert "PumpSwap" in html
    assert "2h old" in html
    assert "https://cdn.example.com/token.png" in html
    assert "https://example.com" in html
    assert "https://t.me/example" in html
    assert "https://x.com/example" in html
    assert 'data-timeframe="1m"' in html
    assert 'data-timeframe="4H"' in html

def test_token_workspace_v243_final_header_cleanup():
    detail = dict(DETAIL)
    detail.update({
        "symbol": "TEST",
        "quote_symbol": "SOL",
        "dex_id": "pumpswap",
        "age": "16h",
        "quote_status": "LIVE",
        "website_url": "https://example.com",
        "telegram_url": "https://t.me/example",
        "twitter_url": "https://x.com/example",
        "change_1m": 0.1,
        "change_5m": 0.2,
        "change_15m": 0.3,
        "change_30m": 0.4,
        "change_1h": 0.5,
        "change_4h": 0.6,
    })

    html = render_solana_discovery_token_page(detail)

    assert "PumpSwap" in html
    assert "16h old" in html
    assert "Website" in html
    assert "Telegram" in html
    assert "Twitter" in html
    assert "Observed price change by trader timeframe" not in html
    assert '<span class="token-info-label">INFO</span>' not in html
    assert "Age unavailable old" not in html

def test_token_workspace_v248_social_links_have_no_orphan_separators():
    base = dict(DETAIL)
    base.update({
        "symbol": "TEST",
        "quote_symbol": "SOL",
        "dex_id": "pumpswap",
        "age": "3h",
        "quote_status": "LIVE",
        "change_1m": 0.1,
        "change_5m": 0.2,
        "change_15m": 0.3,
        "change_30m": 0.4,
        "change_1h": 0.5,
        "change_4h": 0.6,
    })

    only_twitter = dict(base)
    only_twitter.update({
        "website_url": "",
        "telegram_url": "",
        "twitter_url": "https://x.com/example",
    })
    html = render_solana_discovery_token_page(only_twitter)
    card = html.split('class="token-overview-card"', 1)[1].split("</section>", 1)[0]
    assert "Twitter" in card
    assert "Website" not in card
    assert "Telegram" not in card

    website_twitter = dict(base)
    website_twitter.update({
        "website_url": "https://example.com",
        "telegram_url": "",
        "twitter_url": "https://x.com/example",
    })
    html = render_solana_discovery_token_page(website_twitter)
    card = html.split('class="token-overview-card"', 1)[1].split("</section>", 1)[0]
    assert "Website" in card
    assert "Twitter" in card
    assert "Telegram" not in card

    no_socials = dict(base)
    no_socials.update({
        "website_url": "",
        "telegram_url": "",
        "twitter_url": "",
    })
    html = render_solana_discovery_token_page(no_socials)
    card = html.split('class="token-overview-card"', 1)[1].split("</section>", 1)[0]
    assert "token-social-links" not in card
    assert "Website" not in card
    assert "Telegram" not in card
    assert "Twitter" not in card



def test_token_workspace_v25_renders_multitimeframe_candlestick_only():
    detail = dict(DETAIL)
    candle = {
        "time": 1700000000,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }
    detail["candlestick_timeframes"] = {
        "1m": [candle],
        "5m": [candle],
        "15m": [candle],
        "30m": [candle],
        "1H": [candle],
        "4H": [candle],
    }

    html = render_solana_discovery_token_page(detail)

    assert 'data-candlestick-panel' in html
    assert 'data-candle-timeframe="1m"' in html
    assert 'data-candle-timeframe="5m"' in html
    assert 'data-candle-timeframe="15m"' in html
    assert 'data-candle-timeframe="30m"' in html
    assert 'data-candle-timeframe="1H"' in html
    assert 'data-candle-timeframe="4H"' in html
    assert "VALIDATED EXACT-POOL DATA" not in html
    assert "4H Market Chart" not in html
    assert "Closed market intervals; not an executable quote." not in html
    assert "GeckoTerminal" not in html


def test_chart_v21_renders_interactive_trading_controls():
    candle = {
        "time": 1700000000,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }
    detail = dict(DETAIL)
    detail["candlestick_timeframes"] = {
        "1m": [candle],
        "5m": [candle],
        "15m": [candle],
        "30m": [candle],
        "1H": [candle],
        "4H": [candle],
    }

    html = render_solana_discovery_token_page(detail)

    assert "CHART_V21_INTERACTIVE_TRADING_CHART" in html
    assert 'data-candle-ohlc' in html
    assert 'data-ohlc-open' in html
    assert 'data-ohlc-high' in html
    assert 'data-ohlc-low' in html
    assert 'data-ohlc-close' in html
    assert 'data-ohlc-volume' in html
    assert 'data-candle-reset' in html
    assert 'aria-label="Exact-pool interactive candlestick chart"' in html
    assert "candlestick-crosshair" in html
    assert "candlestick-volume" in html
    assert "candlestick-price-line" in html
    assert 'addEventListener("wheel"' in html
    assert 'addEventListener("pointerdown"' in html
    assert 'addEventListener("pointermove"' in html



def test_chart_v22_polls_live_candles_without_page_reload():
    candle = {
        "time": 1700000000,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }
    detail = dict(DETAIL)
    detail["token_address"] = "TokenAddress123456789"
    detail["candlestick_timeframes"] = {
        "1m": [candle],
        "5m": [candle],
        "15m": [candle],
        "30m": [candle],
        "1H": [candle],
        "4H": [candle],
    }

    html = render_solana_discovery_token_page(detail)

    assert "CHART_V22_LIVE_CANDLE" in html
    assert 'data-live-candle-url="/api/discovery/solana/TokenAddress123456789/candles"' in html
    assert 'data-candle-live-state' in html
    assert 'credentials:"same-origin"' in html
    assert 'cache:"no-store"' in html
    assert 'setInterval(()=>pollLive(false),10000)' in html
    assert 'visibilitychange' in html
    assert "location.reload" not in html



def test_chart_v221_keeps_live_builder_on_same_origin_polling_path():
    candle = {
        "time": 1700000000, "open": 1.0, "high": 1.2,
        "low": 0.9, "close": 1.1, "volume": 100.0,
    }
    detail = dict(DETAIL)
    detail["token_address"] = "TokenAddress123456789"
    detail["candlestick_timeframes"] = {
        "1m": [candle], "5m": [candle], "15m": [candle],
        "30m": [candle], "1H": [candle], "4H": [candle],
    }

    html = render_solana_discovery_token_page(detail)

    assert 'data-live-candle-url="/api/discovery/solana/TokenAddress123456789/candles"' in html
    assert 'setInterval(()=>pollLive(false),10000)' in html
    assert 'cache:"no-store"' in html
    assert "location.reload" not in html



# TRANSACTIONS_FEED_V121_ROBUST_UI_MOUNT
def test_transactions_feed_v121_robust_ui_mount():
    candle = {
        "time": 1700000000,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }

    detail = dict(DETAIL)
    detail["token_address"] = "TokenAddress123456789"
    detail["symbol"] = "TEST"
    detail["candlestick_timeframes"] = {
        "1m": [candle],
        "5m": [candle],
        "15m": [candle],
        "30m": [candle],
        "1H": [candle],
        "4H": [candle],
    }

    html = render_solana_discovery_token_page(detail)

    assert "TRANSACTIONS_FEED_V121_ROBUST_UI_MOUNT" in html
    assert 'data-transactions-panel' in html
    assert 'data-transactions-url="/api/discovery/solana/TokenAddress123456789/transactions"' in html
    assert "<h2>Recent Trades</h2>" in html
    assert "<th>Time</th>" in html
    assert "<th>Type</th>" in html
    assert "<th>Price USD</th>" in html
    assert "<th>Amount TEST</th>" in html
    assert "<th>Total USD</th>" in html
    assert "<th>Trader</th>" in html
    assert "<th>Tx</th>" in html
    assert html.index('data-candlestick-panel') < html.index('data-transactions-panel')
    assert 'credentials:"same-origin"' in html
    assert 'cache:"no-store"' in html
    assert "https://solscan.io/tx/" in html
    # TRANSACTIONS_FEED_V131_LEGACY_TEST_ALIGNMENT_ONLY
    # v1.3 supersedes the one-shot loader with immediate forced load + polling.
    assert "loadTransactions(true);" in html



# TRANSACTIONS_FEED_V122_COMPACT_LIVE_TABLE
def test_transactions_feed_v122_compacts_rows_without_vertical_scroll_trap():
    candle = {
        "time": 1700000000,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }
    detail = dict(DETAIL)
    detail["token_address"] = "TokenAddress123456789"
    detail["symbol"] = "TEST"
    detail["candlestick_timeframes"] = {
        "1m": [candle], "5m": [candle], "15m": [candle],
        "30m": [candle], "1H": [candle], "4H": [candle],
    }
    html = render_solana_discovery_token_page(detail)
    assert "TRANSACTIONS_FEED_V122_COMPACT_LIVE_TABLE" in html
    assert ".transactions-table-wrap{max-height:none;overflow-x:auto;overflow-y:visible" in html
    assert "position:sticky" in html
    assert "top:0" in html
    assert "MAX_VISIBLE_TRANSACTIONS=30" in html
    assert "rows.slice(0,MAX_VISIBLE_TRANSACTIONS)" in html
    assert "visibleRows.forEach" in html
    # v1.3 owns loaded-state presentation through LIVE/STALE.
    assert 'setTransactionState(payload.stale===true?"STALE":"LIVE",shown)' in html
    assert "setInterval(loadTransactions" not in html



# TRANSACTIONS_FEED_V1221_UI_SCOPE_FIX
def test_transactions_feed_v1221_defines_rows_before_loaded_state():
    candle = {
        "time": 1700000000,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }

    detail = dict(DETAIL)
    detail["token_address"] = "TokenAddress123456789"
    detail["symbol"] = "TEST"
    detail["candlestick_timeframes"] = {
        "1m": [candle],
        "5m": [candle],
        "15m": [candle],
        "30m": [candle],
        "1H": [candle],
        "4H": [candle],
    }

    html = render_solana_discovery_token_page(detail)

    assert "TRANSACTIONS_FEED_V1221_UI_SCOPE_FIX" in html
    # v1.3 names provider rows `incoming` before exact-id deduplication.
    assert "const incoming=Array.isArray(payload.transactions)" in html
    # TRANSACTIONS_FEED_V1311_SCOPE_TEST_ALIGNMENT
    # v1.3 renders the exact-id deduplicated collection, not raw provider rows.
    assert "renderRows(deduped);" in html
    # TRANSACTIONS_FEED_V1312_FINAL_LEGACY_COUNT_ALIGNMENT
    # v1.3 counts the exact-id deduplicated collection rendered to the table.
    assert "Math.min(deduped.length,MAX_VISIBLE_TRANSACTIONS)" in html

    # TRANSACTIONS_FEED_V1313_FINAL_ORDERING_ALIGNMENT
    # v1.3 defines incoming, deduplicates to deduped, then computes state.
    incoming_pos = html.index("const incoming=Array.isArray(payload.transactions)")
    render_pos = html.index("renderRows(deduped);")
    state_pos = html.index("Math.min(deduped.length,MAX_VISIBLE_TRANSACTIONS)")
    assert incoming_pos < render_pos < state_pos



# TRANSACTIONS_FEED_V13_LIVE_POLLING
def test_transactions_feed_v13_live_polling_preserves_rows_on_failure():
    candle = {
        "time": 1700000000,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
        "volume": 100.0,
    }

    detail = dict(DETAIL)
    detail["token_address"] = "TokenAddress123456789"
    detail["symbol"] = "TEST"
    detail["candlestick_timeframes"] = {
        "1m": [candle],
        "5m": [candle],
        "15m": [candle],
        "30m": [candle],
        "1H": [candle],
        "4H": [candle],
    }

    html = render_solana_discovery_token_page(detail)

    assert "TRANSACTIONS_FEED_V13_LIVE_POLLING" in html
    assert "const POLL_INTERVAL_MS=5000" in html
    assert "let pollInFlight=false" in html
    assert "if(!url||pollInFlight) return" in html
    assert "if(document.hidden&&!force) return" in html
    assert "window.setInterval(()=>loadTransactions(false),POLL_INTERVAL_MS)" in html
    assert 'document.addEventListener("visibilitychange"' in html
    assert 'if(!document.hidden) loadTransactions(true)' in html

    assert "const seen=new Set()" in html
    assert "if(!id||seen.has(id)) return" in html
    assert "seen.add(id)" in html
    assert "MAX_VISIBLE_TRANSACTIONS=30" in html

    assert "function keepExistingRowsOnFailure()" in html
    assert 'tbody.querySelector("tr[data-transaction-id]")' in html

    loader_start = html.index("async function loadTransactions(force=false)")
    loader_end = html.index("loadTransactions(true);", loader_start)
    loader = html[loader_start:loader_end]
    assert "tbody.replaceChildren();" not in loader

    assert 'setTransactionState(payload.stale===true?"STALE":"LIVE",shown)' in html
    assert 'setTransactionState("STALE",existingCount)' in html


def test_transactions_feed_v13_preserves_scroll_anchor_during_live_updates():
    html = render_solana_discovery_token_page(DETAIL)

    assert "function captureScrollAnchor()" in html
    assert "function restoreScrollAnchor(anchor)" in html
    assert "scrollBox.scrollTop<=8" in html
    assert "row.dataset.transactionId===anchor.id" in html
    assert "restoreScrollAnchor(scrollAnchor);" in html



# TRANSACTIONS_FEED_V14_FRESHNESS_DIAGNOSTICS
def test_transactions_feed_v14_renders_freshness_diagnostics():
    html = render_solana_discovery_token_page(DETAIL)

    assert "TRANSACTIONS_FEED_V14_FRESHNESS_DIAGNOSTICS" in html
    assert "function formatFreshnessSeconds(value)" in html
    assert "function applyFreshnessDiagnostics(payload)" in html
    # TRANSACTIONS_FEED_V141_FRESHNESS_SEMANTICS_FIX
    assert "freshness.last_trade_age_seconds" in html
    assert "freshness.api_age_seconds" in html
    assert "freshness.provider_lag_seconds" not in html
    assert 'diagnostics.push("Last trade "+lastTradeAge)' in html
    assert 'diagnostics.push("API age "+apiAge)' in html
    assert 'detail.push("provider lag "+providerLag)' not in html
    assert 'detail.push("cache hit")' in html
    assert 'detail.push("stale fallback")' in html

    state_pos = html.index(
        'setTransactionState(payload.stale===true?"STALE":"LIVE",shown)'
    )
    diagnostics_pos = html.index("applyFreshnessDiagnostics(payload);")
    assert state_pos < diagnostics_pos



# TRANSACTIONS_FEED_V141_FRESHNESS_SEMANTICS_FIX
def test_transactions_feed_v141_hides_internal_row_count_from_user_status():
    html = render_solana_discovery_token_page(DETAIL)

    assert "MAX_VISIBLE_TRANSACTIONS=30" in html
    assert "rows.slice(0,MAX_VISIBLE_TRANSACTIONS)" in html

    assert 'state.textContent=shown ? shown+" recent · LIVE" : "LIVE"' not in html
    assert 'state.textContent=shown ? shown+" recent · STALE" : "STALE"' not in html
    assert 'state.textContent="LIVE"' in html
    assert 'state.textContent="STALE"' in html

    assert '"Last trade "+lastTradeAge' in html
    assert '"API age "+apiAge' in html
    assert "provider lag" not in html



# TOKEN_WORKSPACE_V245_PRECISE_AGE_DISPLAY
def test_token_workspace_v245_formats_subhour_age_in_minutes():
    detail = dict(DETAIL)
    detail.update({"age_hours": 34 / 60, "age": "0h", "pair_age_label": "0h"})
    html = render_solana_discovery_token_page(detail)
    assert "34m old" in html
    assert "0h old" not in html


def test_token_workspace_v245_formats_hour_and_day_age_precisely():
    detail = dict(DETAIL)
    detail["age_hours"] = 1 + (12 / 60)
    assert "1h 12m old" in render_solana_discovery_token_page(detail)
    detail["age_hours"] = 27
    assert "1d 3h old" in render_solana_discovery_token_page(detail)


def test_token_workspace_v245_normalizes_legacy_age_labels():
    detail = dict(DETAIL)
    for key in ("age_hours", "pair_age_hours", "hours_old"):
        detail.pop(key, None)
    detail["age"] = "0.5666667h"
    assert "34m old" in render_solana_discovery_token_page(detail)


def test_token_workspace_v245_keeps_unavailable_age_clean():
    detail = dict(DETAIL)
    for key in (
        "age_hours", "pair_age_hours", "hours_old", "age", "pair_age",
        "age_label", "pair_age_label", "freshness", "freshness_label",
    ):
        detail.pop(key, None)
    html = render_solana_discovery_token_page(detail)
    assert "Age unavailable" in html
    assert "Age unavailable old" not in html


# TOKEN_WORKSPACE_V2453_LEAF_AGE_ICON
def test_token_workspace_v2453_uses_leaf_icon_for_pair_age():
    detail = dict(DETAIL)
    detail["age"] = "1h 5m"

    html = render_solana_discovery_token_page(detail)

    assert "TOKEN_WORKSPACE_V2453_LEAF_AGE_ICON" in html
    assert 'class="token-age-leaf"' in html
    assert 'viewBox="0 0 24 24"' in html
    assert "1h 5m old" in html
    assert '<span aria-hidden="true">&#9201;</span>' not in html


def test_token_workspace_v2453_leaf_icon_is_decorative_and_css_sized():
    html = render_solana_discovery_token_page(DETAIL)

    assert '<svg class="token-age-leaf" aria-hidden="true"' in html
    assert ".token-age-leaf{" in html
    assert "fill:var(--green)" in html



# TRANSACTIONS_FEED_V15_FLOW_INTELLIGENCE
def test_transactions_feed_v15_renders_compact_flow_intelligence():
    html = render_solana_discovery_token_page(DETAIL)

    assert "TRANSACTIONS_FEED_V15_FLOW_INTELLIGENCE" in html
    assert 'data-transactions-flow' in html
    assert 'data-flow-buy-volume' in html
    assert 'data-flow-sell-volume' in html
    assert 'data-flow-net' in html
    assert 'data-flow-largest' in html
    assert "function calculateRecentFlow(rows)" in html
    assert "function renderRecentFlow(rows)" in html


def test_transactions_feed_v15_uses_same_30_row_window_as_table():
    html = render_solana_discovery_token_page(DETAIL)

    assert ".slice(0,MAX_VISIBLE_TRANSACTIONS)" in html
    assert "MAX_VISIBLE_TRANSACTIONS=30" in html
    assert "netFlow:buyVolume-sellVolume" in html
    assert 'side==="BUY"' in html
    assert 'side==="SELL"' in html


def test_transactions_feed_v15_refreshes_flow_after_exact_id_deduplication():
    html = render_solana_discovery_token_page(DETAIL)

    dedupe_pos = html.index("deduped.push(item);")
    rows_pos = html.index("renderRows(deduped);")
    flow_pos = html.index("renderRecentFlow(deduped);")

    assert dedupe_pos < rows_pos < flow_pos


def test_transactions_feed_v15_failure_keeps_last_rendered_flow():
    html = render_solana_discovery_token_page(DETAIL)

    load_pos = html.index("async function loadTransactions")
    catch_pos = html.index("}catch(error){", load_pos)
    catch_end = html.index("}finally{", catch_pos)
    catch_block = html[catch_pos:catch_end]

    assert "renderRecentFlow" not in catch_block
    assert "keepExistingRowsOnFailure();" in catch_block



# TRANSACTIONS_FEED_V151_FLOW_VISUAL_FINAL
def test_transactions_feed_v151_final_colors_largest_trade_by_side():
    html = render_solana_discovery_token_page(DETAIL)

    assert "TRANSACTIONS_FEED_V151_FLOW_VISUAL_FINAL" in html
    assert ".flow-largest-tone.buy{color:var(--green)!important}" in html
    assert ".flow-largest-tone.sell{color:var(--red)!important}" in html
    assert 'class="flow-largest-tone" data-flow-largest' in html
    assert 'class="flow-largest-tone" data-flow-largest-side' in html
    assert 'node.classList.add(flow.largest.side.toLowerCase())' in html


def test_transactions_feed_v151_final_adds_live_volume_visuals():
    html = render_solana_discovery_token_page(DETAIL)

    assert 'data-flow-buy-meter' in html
    assert 'data-flow-sell-meter' in html
    assert 'data-flow-bias' in html
    assert "const totalVolume=flow.buyVolume+flow.sellVolume;" in html
    assert "(flow.buyVolume/totalVolume)*100" in html
    assert "(flow.sellVolume/totalVolume)*100" in html
    assert '"Buy pressure"' in html
    assert '"Sell pressure"' in html
    assert '"Balanced"' in html


def test_transactions_feed_v151_final_preserves_v15_calculation_and_polling():
    html = render_solana_discovery_token_page(DETAIL)

    assert "netFlow:buyVolume-sellVolume" in html
    assert "MAX_VISIBLE_TRANSACTIONS=30" in html
    assert "const POLL_INTERVAL_MS=5000;" in html
    assert "renderRecentFlow(deduped);" in html



# CHART_V23_TRADE_OVERLAY
def test_chart_v23_trade_overlay_maps_recent_transactions_to_candles():
    html = render_solana_discovery_token_page(DETAIL)

    assert "CHART_V23_TRADE_OVERLAY" in html
    assert 'const TIMEFRAME_SECONDS={"1m":60,"5m":300,"15m":900,"30m":1800,"1H":3600,"4H":14400};' in html
    assert "function tradeOverlayBuckets(rows,timeframe)" in html
    assert "candleBucket(ts,timeframe)" in html
    assert "drawTradeOverlay(visible,slot,left,y);" in html


def test_chart_v23_trade_overlay_has_buy_sell_markers_and_tooltip():
    html = render_solana_discovery_token_page(DETAIL)

    assert ".candlestick-trade-marker.buy" in html
    assert ".candlestick-trade-marker.sell" in html
    assert 'class:"candlestick-trade-marker "+side.toLowerCase()' in html
    assert "function showTradeTooltip(event,summary)" in html
    assert 'title.textContent=summary.side+" · "+tradeUsd(total);' in html


def test_chart_v23_trade_overlay_refreshes_from_live_transactions():
    html = render_solana_discovery_token_page(DETAIL)

    assert 'window.addEventListener("dexsato:transactions-updated"' in html
    assert 'window.dispatchEvent(new CustomEvent("dexsato:transactions-updated"' in html
    assert "detail:{transactions:deduped.slice(0,MAX_VISIBLE_TRANSACTIONS)}" in html
    assert "const POLL_INTERVAL_MS=5000;" in html


def test_chart_v23_trade_overlay_preserves_existing_chart_controls():
    html = render_solana_discovery_token_page(DETAIL)

    assert "CHART_V21_INTERACTIVE_TRADING_CHART" in html
    assert "CHART_V22_LIVE_CANDLE" in html
    assert 'state.visibleCount=clamp(state.visibleCount+(event.deltaY>0?6:-6)' in html
    assert 'button.dataset.candleTimeframe' in html



# CHART_V24_TRADE_SIZE_INTELLIGENCE
def test_chart_v24_trade_size_uses_relative_recent_distribution():
    html = render_solana_discovery_token_page(DETAIL)

    assert "CHART_V24_TRADE_SIZE_INTELLIGENCE" in html
    assert "function tradeSizeThresholds(values)" in html
    assert "p50:quantile(.50)" in html
    assert "p80:quantile(.80)" in html
    assert "function tradeSizeLabel(value,thresholds)" in html
    assert 'if(n>thresholds.p80) return "LARGE"' in html
    assert 'if(n>thresholds.p50) return "MEDIUM"' in html


def test_chart_v24_trade_size_changes_marker_size_without_moving_overlay():
    html = render_solana_discovery_token_page(DETAIL)

    assert 'const radius=size==="LARGE"?8:size==="MEDIUM"?6:4.5;' in html
    assert '" size-"+size.toLowerCase()' in html
    assert ".candlestick-trade-marker.size-small" in html
    assert ".candlestick-trade-marker.size-medium" in html
    assert ".candlestick-trade-marker.size-large" in html
    # v2.3 positioning remains untouched.
    assert 'const markerY=side==="BUY"?y(anchor)+12:y(anchor)-12;' in html


def test_chart_v24_trade_size_tooltip_discloses_size_class():
    html = render_solana_discovery_token_page(DETAIL)

    assert 'detail.textContent="Trade size: "+summary.size' in html
    assert 'showTradeTooltip(event,{side,trades,total,size})' in html


def test_chart_v24_preserves_v23_trade_mapping_and_live_wiring():
    html = render_solana_discovery_token_page(DETAIL)

    assert "CHART_V23_TRADE_OVERLAY" in html
    assert "function tradeOverlayBuckets(rows,timeframe)" in html
    assert 'window.addEventListener("dexsato:transactions-updated"' in html
    assert 'window.dispatchEvent(new CustomEvent("dexsato:transactions-updated"' in html
    assert "const POLL_INTERVAL_MS=5000;" in html


# TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI
def test_transactions_v16b_renders_market_activity_ui():
    html=render_solana_discovery_token_page(DETAIL)
    assert "TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI" in html
    assert "Market Activity" in html and "Exact-pool broader participation" not in html
    assert "Exact-pool aggregate" in html
    assert "GeckoTerminal" not in html
    assert "30 latest exact-pool trades" in html
    assert '["buys","activity-buys",activityNumber]' in html
    assert '["volume_usd","activity-volume",activityUsd]' in html
    assert 'renderMarketActivity(payload.market_activity);' in html


def test_transactions_v26b_places_readable_market_activity_summary_after_trades():
    html=render_solana_discovery_token_page(DETAIL)

    assert html.index('data-transactions-body') < html.index('data-market-activity aria-label=')
    assert '.market-activity-head span{display:block;color:var(--text);font:750 12px/1.25 var(--mono)' in html
    assert '.market-activity-table th,.market-activity-table td{padding:10px 12px' in html
    assert 'font:12px/1.35 var(--mono)' in html


def test_tw_dex_05_renders_rounded_flow_trades_and_activity_layout_without_new_data():
    html=render_solana_discovery_token_page(DETAIL)

    assert "TW-DEX-05 — Flow, Recent Trades and Market Activity presentation" in html
    assert 'class="transactions-flow-item buy"' in html
    assert 'class="transactions-flow-item sell"' in html
    assert 'class="transactions-flow-item net"' in html
    assert 'class="transactions-flow-item largest"' in html
    assert 'class="transactions-detail-grid"' in html
    assert 'class="recent-trades-card"' in html
    assert "<h2>Recent Trades</h2>" in html
    assert "<th>Window</th><th>Buy</th><th>Sell</th><th>Trades</th><th>Volume</th>" in html
    assert 'const MARKET_ACTIVITY_WINDOWS=[["m5","5M"],["m15","15M"],["m30","30M"],["h1","1H"],["h6","6H"],["h24","24H"]]' in html
    assert 'const specs=[["buys","activity-buys",activityNumber],["sells","activity-sells",activityNumber],["total_transactions","activity-total",activityNumber],["volume_usd","activity-volume",activityUsd]]' in html
    assert ".recent-trades-card,.market-activity{min-width:0;overflow:hidden;border:1px solid #2a3948;border-radius:11px" in html
    assert "font:800 16px/1.15 var(--mono)" in html
    assert ".transactions-table th:nth-child(6),.transactions-table td:nth-child(6){display:none}" in html
    assert "netFlow:buyVolume-sellVolume" in html
    assert "const POLL_INTERVAL_MS=5000;" in html


def test_tw_dex_05a_polishes_market_activity_without_changing_data_contract():
    html=render_solana_discovery_token_page(DETAIL)

    assert "TW-DEX-05A — Market Activity visual polish" in html
    assert "Exact-pool broader participation" not in html
    assert '.market-activity{border-color:#1d2733;background:#0e141c}' in html
    assert '.market-activity-wrap{overflow-x:hidden}' in html
    assert '.market-activity-table{width:100%;min-width:0;background:#10171f}' in html
    assert 'border-right:0!important;border-bottom:0!important' in html
    assert '.market-activity-table td.activity-buys{color:#4cf4d6}' in html
    assert '.market-activity-table td.activity-sells{color:#ff5c7a}' in html
    assert '.market-activity-table td.activity-total,.market-activity-table td.activity-volume{color:#e7edf4;font-weight:800}' in html
    assert 'const MARKET_ACTIVITY_WINDOWS=[["m5","5M"],["m15","15M"],["m30","30M"],["h1","1H"],["h6","6H"],["h24","24H"]]' in html
    assert 'const specs=[["buys","activity-buys",activityNumber],["sells","activity-sells",activityNumber],["total_transactions","activity-total",activityNumber],["volume_usd","activity-volume",activityUsd]]' in html
    assert 'renderMarketActivity(payload.market_activity);' in html
    assert "const POLL_INTERVAL_MS=5000;" in html
