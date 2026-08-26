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

def test_renders_controlled_non_custodial_jupiter_swap_and_discloses_risk():
    html = render_solana_discovery_token_page(DETAIL)
    assert "Jupiter integration sandbox" in html
    assert "Controlled wallet-approved swap" in html
    assert "D6 · NON-CUSTODIAL PILOT" in html
    assert "Connect supported wallet" in html
    assert "Get Jupiter quote" in html
    assert "Real Solana mainnet transaction" in html
    assert "review the transaction in my own wallet" in html
    assert 'data-swap-risk-ack' in html
    assert 'data-execute-swap disabled' in html
    assert 'data-token-symbol="TEST"' in html
    assert 'src="/static/js/dexsato_solana_discovery_swap.js" defer' in html
    assert "DexSato integrator fee: <strong>0 bps</strong>" in html
    assert "Pool verification is not token verification" in html
    assert "does not hold private keys or funds" in html
    assert "Transactions must be approved in your connected wallet" in html
    assert html.index("Risk context") < html.index("Qualification evidence")
    assert html.index("Qualification evidence") < html.index("Jupiter integration sandbox")
    assert 'class="card jupiter" data-jupiter-sandbox' in html



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
    assert "Retry signed transaction" in script
    assert "credentials: \"same-origin\"" in script
    assert "x-api-key" not in script
    assert "privateKey" not in script and "seedPhrase" not in script



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
    assert 'localStorage.getItem("dexsato-theme")' in html


def test_token_workspace_v2_decision_layout_is_ui_only():
    html = render_solana_discovery_token_page({
        "symbol": "EX", "name": "Example", "quote_symbol": "SOL",
        "token_address": "token-address", "pair_address": "pair-address",
        "dex_id": "pumpswap", "quote_status": "LIVE",
        "quote_label": "Live exact-pool observation", "chart": [],
    })
    assert "Token Workspace v2 Decision Layout" in html
    assert "dexsato-evidence-strip" in html
    assert "decision-grid-v2" in html
    assert "Not independently verified" in html
    assert "Controlled wallet-approved swap" in html
    assert "Get Jupiter quote" in html


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
    assert "<h2>Transactions</h2>" in html
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
def test_transactions_feed_v122_compacts_rows_and_keeps_internal_scroll():
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
    assert "max-height:480px" in html
    assert "overflow:auto" in html
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
