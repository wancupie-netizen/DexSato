from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import application.solana_discovery_token_service as token_service

from application.solana_discovery_token_service import load_solana_discovery_token


TOKEN = "TokenAddressCaseSensitive123"
POOL = "PoolAddress123"
FEED = {
    "updated_label": "4 min ago",
    "candidates": [{
        "token_address": TOKEN, "pair_address": POOL, "symbol": "TEST",
        "name": "Test Token", "price_usd": 0.1, "liquidity_usd": 6000,
        "volume_24h_usd": 2000,
    }],
}


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_returns_only_exact_qualified_token_and_validates_live_pair():
    def get(url, **kwargs):
        if "dexscreener" in url:
            return Response({"pairs": [{
                "pairAddress": POOL, "baseToken": {"address": TOKEN},
                "priceUsd": "0.12", "liquidity": {"usd": 7000},
                "volume": {"h24": 3000}, "priceChange": {"h24": 4.5},
                "marketCap": 120000, "dexId": "raydium",
                "url": "https://dexscreener.com/solana/pool",
            }]})
        return Response({"data": {"attributes": {"ohlcv_list": [
            [2, .1, .13, .09, .12, 100], [1, .09, .11, .08, .1, 80]
        ]}}})

    result = load_solana_discovery_token(TOKEN, feed=FEED, request_get=get)

    assert result["quote_status"] == "LIVE"
    assert result["price_usd"] == .12
    assert result["pair_address"] == POOL
    assert len(result["chart"]) == 2


def test_token_observation_reads_mint_and_freeze_authority_from_solana_rpc():
    def get(url, **kwargs):
        if "dexscreener" in url:
            return Response({"pairs": []})
        return Response({"data": {"attributes": {"ohlcv_list": []}}})
    def post(url, **kwargs):
        return Response({"result": {"value": {"data": {"parsed": {"info": {
            "mintAuthority": None, "freezeAuthority": "AuthorityAddress123"
        }}}}}})
    result = load_solana_discovery_token(TOKEN, feed=FEED, request_get=get, request_post=post)
    assert result["mint_authority_observation"] == "Revoked"
    assert result["freeze_authority_observation"] == "Active"
    assert result["metadata_observation"] == "Unavailable"


def test_rejects_unknown_or_case_changed_token():
    assert load_solana_discovery_token("unknown", feed=FEED) is None
    assert load_solana_discovery_token(TOKEN.lower(), feed=FEED) is None


def test_falls_back_to_stored_observation_when_provider_fails():
    def fail(*args, **kwargs):
        raise RuntimeError("provider failed")

    result = load_solana_discovery_token(TOKEN, feed=FEED, request_get=fail)

    assert result["quote_status"] == "STORED"
    assert result["price_usd"] == .1
    assert result["chart"] == []


@patch("application.solana_discovery_token_service.load_solana_discovery_record")
def test_loads_persistent_archive_record_without_requiring_front_feed(mock_record):
    mock_record.return_value = {
        **FEED["candidates"][0],
        "currently_qualified": False,
        "current_qualification": {
            "title": "Not evaluated in this scan",
            "message": "The rotating scan did not select this token.",
        },
    }

    def fail(*args, **kwargs):
        raise RuntimeError("provider failed")

    result = load_solana_discovery_token(TOKEN, request_get=fail, request_post=fail)

    assert result is not None
    assert result["token_address"] == TOKEN
    assert result["currently_qualified"] is False
    assert result["feed_updated_label"] == "Unknown"

def test_trader_timeframe_changes_uses_closed_minute_history():
    from application.solana_discovery_token_service import _trader_timeframe_changes

    base_time = 1_700_000_000
    candles = [
        {
            "time": base_time + minute * 60,
            "open": 100.0 + minute,
            "high": 100.0 + minute,
            "low": 100.0 + minute,
            "close": 100.0 + minute,
            "volume": 1.0,
        }
        for minute in range(0, 301)
    ]

    changes = _trader_timeframe_changes(candles)
    newest = 400.0

    assert changes["change_1m"] == ((newest / 399.0) - 1.0) * 100.0
    assert changes["change_5m"] == ((newest / 395.0) - 1.0) * 100.0
    assert changes["change_15m"] == ((newest / 385.0) - 1.0) * 100.0
    assert changes["change_30m"] == ((newest / 370.0) - 1.0) * 100.0
    assert changes["change_1h"] == ((newest / 340.0) - 1.0) * 100.0
    assert changes["change_4h"] == ((newest / 160.0) - 1.0) * 100.0


def test_trader_timeframe_changes_keeps_missing_history_unavailable():
    from application.solana_discovery_token_service import _trader_timeframe_changes

    base_time = 1_700_000_000
    candles = [
        {
            "time": base_time + minute * 60,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0 + minute / 100.0,
            "volume": 1.0,
        }
        for minute in range(0, 11)
    ]

    changes = _trader_timeframe_changes(candles)

    assert changes["change_1m"] is not None
    assert changes["change_5m"] is not None
    assert changes["change_15m"] is None
    assert changes["change_30m"] is None
    assert changes["change_1h"] is None
    assert changes["change_4h"] is None



def test_candlestick_timeframes_aggregate_real_ohlcv():
    from application.solana_discovery_token_service import _candlestick_timeframes

    minute = [
        {
            "time": 1_700_000_000 + index * 60,
            "open": 10.0 + index,
            "high": 11.0 + index,
            "low": 9.0 + index,
            "close": 10.5 + index,
            "volume": 100.0,
        }
        for index in range(30)
    ]
    hourly = [{
        "time": 1_700_000_000,
        "open": 10.0, "high": 20.0, "low": 9.0, "close": 18.0, "volume": 500.0,
    }]
    four_hour = [{
        "time": 1_700_000_000,
        "open": 10.0, "high": 30.0, "low": 8.0, "close": 25.0, "volume": 900.0,
    }]

    result = _candlestick_timeframes(minute, hourly, four_hour)

    assert len(result["1m"]) == 30
    assert len(result["5m"]) >= 6
    assert len(result["15m"]) >= 2
    assert len(result["30m"]) >= 1
    assert result["1H"] == hourly
    assert result["4H"] == four_hour



def test_live_candle_loader_fetches_only_requested_timeframe():
    from application.solana_discovery_token_service import load_solana_discovery_live_candles

    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "attributes": {
                        "ohlcv_list": [
                            [1700000300, 1.1, 1.3, 1.0, 1.2, 200],
                            [1700000000, 1.0, 1.2, 0.9, 1.1, 100],
                        ]
                    }
                }
            }

    def request_get(url, params=None, timeout=10):
        calls.append((url, params))
        return Response()

    feed = {
        "candidates": [{
            "token_address": "token-address",
            "pair_address": "pair-address",
        }]
    }

    result = load_solana_discovery_live_candles(
        "token-address",
        "5m",
        feed=feed,
        request_get=request_get,
    )

    assert result is not None
    assert result["timeframe"] == "5m"
    assert isinstance(result["candles"], list)
    # CHART_V221_TEST_ALIGNMENT
    # Exactly one OHLCV read plus one exact-pool live-price read.
    assert len(calls) == 2

    ohlcv_calls = [(url, params) for url, params in calls if "api.geckoterminal.com" in url]
    exact_pool_calls = [(url, params) for url, params in calls if "api.dexscreener.com" in url]

    assert len(ohlcv_calls) == 1
    assert len(exact_pool_calls) == 1

    ohlcv_url, ohlcv_params = ohlcv_calls[0]
    assert ohlcv_url.endswith("/pools/pair-address/ohlcv/minute")
    assert ohlcv_params == {
        "aggregate": 1,
        "limit": 300,
        "currency": "usd",
        "token": "token-address",
    }

    exact_pool_url, exact_pool_params = exact_pool_calls[0]
    assert exact_pool_url.endswith("/pairs/solana/pair-address")
    assert exact_pool_params is None
    assert "/ohlcv/minute" in calls[0][0]
    assert calls[0][1]["aggregate"] == 1


def test_live_candle_loader_rejects_unknown_timeframe():
    import pytest
    from application.solana_discovery_token_service import load_solana_discovery_live_candles

    with pytest.raises(ValueError):
        load_solana_discovery_live_candles(
            "token-address",
            "2H",
            feed={"candidates": []},
        )



# CHART_V221_LIVE_CANDLE_BUILDER
def test_live_candle_builder_updates_open_bucket_from_exact_pool_price():
    from application.solana_discovery_token_service import _merge_live_price_into_candles

    candles = [{
        "time": 1700000040.0, "open": 1.00, "high": 1.10,
        "low": 0.95, "close": 1.05, "volume": 123.0,
    }]
    merged, used = _merge_live_price_into_candles(candles, "1m", 1.20, 1700000055.0)

    assert used is True
    assert len(merged) == 1
    assert merged[-1]["open"] == 1.00
    assert merged[-1]["high"] == 1.20
    assert merged[-1]["low"] == 0.95
    assert merged[-1]["close"] == 1.20
    assert merged[-1]["volume"] == 123.0
    assert merged[-1]["live"] is True
    assert merged[-1]["volume_live"] is False


def test_live_candle_builder_opens_new_bucket_without_fabricating_volume():
    from application.solana_discovery_token_service import _merge_live_price_into_candles

    candles = [{
        "time": 1699999980.0, "open": 1.00, "high": 1.10,
        "low": 0.95, "close": 1.05, "volume": 123.0,
    }]
    merged, used = _merge_live_price_into_candles(candles, "1m", 1.15, 1700000055.0)

    assert used is True
    assert len(merged) == 2
    assert merged[-1]["time"] == 1700000040.0
    assert merged[-1]["open"] == 1.15
    assert merged[-1]["high"] == 1.15
    assert merged[-1]["low"] == 1.15
    assert merged[-1]["close"] == 1.15
    assert merged[-1]["volume"] is None
    assert merged[-1]["volume_live"] is False


def test_live_candle_builder_never_rewrites_future_provider_history():
    from application.solana_discovery_token_service import _merge_live_price_into_candles

    candles = [{
        "time": 1700000100.0, "open": 1.00, "high": 1.10,
        "low": 0.95, "close": 1.05, "volume": 123.0,
    }]
    merged, used = _merge_live_price_into_candles(candles, "1m", 2.00, 1700000055.0)

    assert used is False
    assert merged == candles


def test_live_candle_builder_does_not_create_history_from_current_price_only():
    from application.solana_discovery_token_service import _merge_live_price_into_candles

    merged, used = _merge_live_price_into_candles([], "5m", 0.00000299924, 1700000055.0)

    assert merged == []
    assert used is False


def test_ohlcv_normalizer_keeps_valid_flat_candles_and_deduplicates_timestamp():
    from application.solana_discovery_token_service import _normalize_ohlcv_rows

    rows = [
        [1700000060, 2.0, 2.0, 2.0, 2.0, 4.0],
        [1700000000, 1.0, 1.2, 0.9, 1.1, 3.0],
        [1700000000, 9.0, 9.5, 8.5, 9.1, 8.0],
        [1700000120, 1.0, 0.9, 1.1, 1.0, 2.0],
    ]

    result = _normalize_ohlcv_rows(rows)

    assert [row["time"] for row in result] == [1700000000.0, 1700000060.0]
    assert result[0]["open"] == 1.0
    assert result[1] == {
        "time": 1700000060.0,
        "open": 2.0,
        "high": 2.0,
        "low": 2.0,
        "close": 2.0,
        "volume": 4.0,
    }


def test_every_ohlcv_provider_requests_the_exact_target_token_address():
    from application.solana_discovery_token_service import (
        _chart_provider,
        _hourly_candles_provider,
        _minute_candles_provider,
    )

    calls = []

    class OhlcvResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"attributes": {"ohlcv_list": [
                [1700000000, 1.0, 1.0, 1.0, 1.0, 0.0],
            ]}}}

    def get(url, params=None, timeout=10):
        calls.append((url, params, timeout))
        return OhlcvResponse()

    candidate = {
        "pair_address": "shared-pair",
        "token_address": "exact-target-token",
    }

    assert _chart_provider(candidate, get)
    assert _minute_candles_provider(candidate, get)
    assert _hourly_candles_provider(candidate, get)
    assert len(calls) == 3
    assert all(params["token"] == "exact-target-token" for _, params, _ in calls)
    assert all(timeout == 10 for _, _, timeout in calls)



# TRANSACTIONS_FEED_V10_EXACT_POOL_SERVICE
def test_transactions_service_fetches_only_exact_qualified_pool():
    from application.solana_discovery_token_service import load_solana_discovery_transactions
    calls = []

    class TradesResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": [{
                "id": "solana_trade_1",
                "type": "trade",
                "attributes": {
                    "block_timestamp": "2026-08-26T00:00:10Z",
                    "tx_hash": "tx-buy",
                    "tx_from_address": "wallet-buy",
                    "from_token_amount": "0.5",
                    "to_token_amount": "1000",
                    "price_from_in_usd": "200",
                    "price_to_in_usd": "0.1",
                    "volume_in_usd": "100",
                    "from_token_address": "So11111111111111111111111111111111111111112",
                    "to_token_address": TOKEN,
                    "kind": "buy",
                },
            }]}

    def get(url, params=None, timeout=10):
        calls.append((url, params, timeout))
        return TradesResponse()

    result = load_solana_discovery_transactions(TOKEN, feed=FEED, request_get=get)

    assert result is not None
    assert result["token_address"] == TOKEN
    assert result["pair_address"] == POOL
    assert len(calls) == 2
    trades_call, aggregate_call = calls
    assert trades_call[0].endswith(f"/networks/solana/pools/{POOL}/trades")
    assert trades_call[1] == {"token": "base"}
    assert trades_call[2] == 10
    assert aggregate_call[0].endswith(f"/networks/solana/pools/{POOL}")
    assert aggregate_call[1] is None
    assert aggregate_call[2] == 10
    assert all(f"/networks/solana/pools/{POOL}" in url for url, _, _ in calls)
    trade = result["transactions"][0]
    assert trade["side"] == "BUY"
    assert trade["token_amount"] == 1000.0
    assert trade["price_usd"] == 0.1
    assert trade["volume_usd"] == 100.0
    assert trade["trader"] == "wallet-buy"


def test_transactions_service_derives_sell_from_exact_token_direction():
    from application.solana_discovery_token_service import _normalize_exact_pool_trade
    row = {
        "id": "solana_trade_2",
        "attributes": {
            "block_timestamp": "2026-08-26T00:00:20Z",
            "tx_hash": "tx-sell",
            "tx_from_address": "wallet-sell",
            "from_token_amount": "2500",
            "to_token_amount": "1.25",
            "price_from_in_usd": "0.05",
            "price_to_in_usd": "100",
            "volume_in_usd": "125",
            "from_token_address": TOKEN,
            "to_token_address": "So11111111111111111111111111111111111111112",
            "kind": "buy",
        },
    }
    trade = _normalize_exact_pool_trade(row, TOKEN)
    assert trade is not None
    assert trade["side"] == "SELL"
    assert trade["token_amount"] == 2500.0
    assert trade["price_usd"] == 0.05
    assert trade["volume_usd"] == 125.0


def test_transactions_service_rejects_trade_not_involving_exact_token():
    from application.solana_discovery_token_service import _normalize_exact_pool_trade
    row = {
        "id": "wrong-token-trade",
        "attributes": {
            "block_timestamp": "2026-08-26T00:00:30Z",
            "tx_hash": "tx-wrong",
            "tx_from_address": "wallet",
            "from_token_amount": "1",
            "to_token_amount": "2",
            "price_from_in_usd": "1",
            "price_to_in_usd": "1",
            "volume_in_usd": "2",
            "from_token_address": "other-a",
            "to_token_address": "other-b",
        },
    }
    assert _normalize_exact_pool_trade(row, TOKEN) is None


def test_transactions_service_deduplicates_by_provider_trade_identity():
    from application.solana_discovery_token_service import _normalize_exact_pool_trades
    row = {
        "id": "same-trade-id",
        "attributes": {
            "block_timestamp": "2026-08-26T00:00:40Z",
            "tx_hash": "same-tx",
            "tx_from_address": "wallet",
            "from_token_amount": "1",
            "to_token_amount": "10",
            "price_from_in_usd": "10",
            "price_to_in_usd": "1",
            "volume_in_usd": "10",
            "from_token_address": "quote-token",
            "to_token_address": TOKEN,
        },
    }
    result = _normalize_exact_pool_trades({"data": [row, dict(row)]}, TOKEN)
    assert len(result) == 1
    assert result[0]["id"] == "same-trade-id"


def test_transactions_service_rejects_unknown_or_case_changed_token():
    from application.solana_discovery_token_service import load_solana_discovery_transactions
    assert load_solana_discovery_transactions("unknown", feed=FEED) is None
    assert load_solana_discovery_transactions(TOKEN.lower(), feed=FEED) is None


def test_transactions_service_fails_closed_for_malformed_provider_payload():
    from application.solana_discovery_token_service import load_solana_discovery_transactions

    class BadResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"data": "not-a-list"}

    result = load_solana_discovery_transactions(
        TOKEN,
        feed=FEED,
        request_get=lambda *args, **kwargs: BadResponse(),
    )
    assert result is not None
    assert result["transactions"] == []


# TW-DATA-01A_EXACT_POOL_FALLBACK
def test_empty_gecko_ohlcv_uses_configured_birdeye_exact_pair(monkeypatch):
    from application.solana_discovery_token_service import _minute_candles_provider

    monkeypatch.setenv("BIRDEYE_API_KEY", "server-side-test-key")
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if "geckoterminal" in url:
            return Response({"data": {"attributes": {"ohlcv_list": []}}})
        return Response({
            "success": True,
            "data": {"items": [
                {"unixTime": 1700000060, "o": 1.1, "h": 1.3, "l": 1.0, "c": 1.2, "v": 20},
                {"unixTime": 1700000000, "o": 1.0, "h": 1.2, "l": 0.9, "c": 1.1, "v": 10},
            ]},
        })

    rows = _minute_candles_provider(FEED["candidates"][0], get)

    assert [row["time"] for row in rows] == [1700000000.0, 1700000060.0]
    assert len(calls) == 2
    fallback_url, fallback_kwargs = calls[1]
    assert fallback_url == token_service.BIRDEYE_OHLCV_PAIR_URL
    assert fallback_kwargs["params"]["address"] == POOL
    assert fallback_kwargs["params"]["type"] == "1m"
    assert fallback_kwargs["headers"] == {
        "X-API-KEY": "server-side-test-key", "x-chain": "solana",
    }


def test_empty_gecko_transactions_use_birdeye_exact_pool_only(monkeypatch):
    from application.solana_discovery_token_service import load_solana_discovery_transactions

    monkeypatch.setenv("BIRDEYE_API_KEY", "server-side-test-key")
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url == token_service.BIRDEYE_TRADES_PAIR_URL:
            return Response({
                "success": True,
                "data": {"items": [{
                    "poolId": POOL,
                    "txHash": "birdeye-tx-1",
                    "blockUnixTime": 1700000000,
                    "owner": "wallet-1",
                    "volumeUSD": 12.5,
                    "from": {"address": "quote-token", "uiAmount": 0.5, "price": 25},
                    "to": {"address": TOKEN, "uiAmount": 125, "price": 0.1},
                }]},
            })
        if url.endswith(f"/pools/{POOL}/trades"):
            return Response({"data": []})
        return Response({"data": {"id": f"solana_{POOL}", "attributes": {"address": POOL}}})

    result = load_solana_discovery_transactions(TOKEN, feed=FEED, request_get=get)

    assert result is not None
    assert result["source"] == "Birdeye exact-pool trades fallback"
    assert result["transactions"] == [{
        "id": "birdeye-tx-1",
        "tx_hash": "birdeye-tx-1",
        "timestamp": "2023-11-14T22:13:20Z",
        "trader": "wallet-1",
        "side": "BUY",
        "price_usd": 0.1,
        "token_amount": 125.0,
        "volume_usd": 12.5,
    }]
    fallback_calls = [item for item in calls if item[0] == token_service.BIRDEYE_TRADES_PAIR_URL]
    assert len(fallback_calls) == 1
    assert fallback_calls[0][1]["params"]["address"] == POOL


def test_birdeye_trade_fallback_rejects_wrong_pool_and_wrong_token():
    normalize = token_service._normalize_birdeye_exact_pool_trades
    valid_shape = {
        "poolId": "wrong-pool",
        "txHash": "tx",
        "blockUnixTime": 1700000000,
        "volumeUSD": 1,
        "from": {"address": "quote", "uiAmount": 1, "price": 1},
        "to": {"address": TOKEN, "uiAmount": 1, "price": 1},
    }
    assert normalize({"success": True, "data": {"items": [valid_shape]}}, TOKEN, POOL) == []

    wrong_token = dict(valid_shape)
    wrong_token["poolId"] = POOL
    wrong_token["to"] = {"address": "other-token", "uiAmount": 1, "price": 1}
    assert normalize({"success": True, "data": {"items": [wrong_token]}}, TOKEN, POOL) == []



# TRANSACTIONS_FEED_V123_PROVIDER_RESILIENCE
def test_provider_resilience_reuses_minute_ohlcv_cache(monkeypatch):
    import requests
    import application.solana_discovery_token_service as service

    service._OHLCV_CACHE.clear()
    calls = []

    def provider(candidate, request_get):
        calls.append(candidate["pair_address"])
        return [{
            "time": 1700000000.0,
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.05,
            "volume": 100.0,
        }]

    monkeypatch.setattr(service, "_minute_candles_provider", provider)
    candidate = {"pair_address": "cache-pair", "token_address": "cache-token"}

    first = service._minute_candles(candidate, requests.get)
    second = service._minute_candles(candidate, requests.get)

    assert first == second
    assert calls == ["cache-pair"]


def test_provider_resilience_separates_ohlcv_cache_by_target_token(monkeypatch):
    import requests
    import application.solana_discovery_token_service as service

    service._OHLCV_CACHE.clear()
    calls = []

    def provider(candidate, request_get):
        calls.append(candidate["token_address"])
        price = 1.0 if candidate["token_address"] == "base-token" else 2.0
        return [{
            "time": 1700000000.0,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 1.0,
        }]

    monkeypatch.setattr(service, "_minute_candles_provider", provider)
    base = {"pair_address": "shared-pair", "token_address": "base-token"}
    quote = {"pair_address": "shared-pair", "token_address": "quote-token"}

    assert service._minute_candles(base, requests.get)[0]["close"] == 1.0
    assert service._minute_candles(quote, requests.get)[0]["close"] == 2.0
    assert calls == ["base-token", "quote-token"]


def test_provider_resilience_uses_stale_ohlcv_when_refresh_fails(monkeypatch):
    import requests
    import application.solana_discovery_token_service as service

    service._OHLCV_CACHE.clear()
    candidate = {"pair_address": "stale-pair", "token_address": "stale-token"}
    cached_rows = [{
        "time": 1700000000.0,
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.05,
        "volume": 100.0,
    }]
    service._OHLCV_CACHE[("stale-pair", "stale-token", "minute")] = (
        service.monotonic() - 90.0,
        cached_rows,
    )

    def failing_provider(candidate, request_get):
        raise requests.RequestException("temporary provider failure")

    monkeypatch.setattr(service, "_minute_candles_provider", failing_provider)

    result = service._minute_candles(candidate, requests.get)

    assert result == cached_rows


def test_provider_resilience_transactions_fall_back_to_last_valid_payload(monkeypatch):
    import requests
    import application.solana_discovery_token_service as service

    service._TRANSACTION_CACHE.clear()
    token = "CacheToken123"
    cached = {
        "token_address": token,
        "pair_address": "CachePool123",
        "transactions": [{"id": "trade-1", "side": "BUY"}],
        "as_of": "2026-08-26T00:00:00+00:00",
        "source": "GeckoTerminal exact-pool trades",
    }
    service._TRANSACTION_CACHE[token] = (
        service.monotonic() - 60.0,
        cached,
    )

    def failing_provider(*args, **kwargs):
        raise requests.RequestException("temporary provider failure")

    monkeypatch.setattr(
        service,
        "_load_solana_discovery_transactions_provider",
        failing_provider,
    )

    result = service.load_solana_discovery_transactions(token)

    assert result is not None
    assert result["transactions"] == [{"id": "trade-1", "side": "BUY"}]
    assert result["stale"] is True



# TRANSACTIONS_FEED_V14_FRESHNESS_DIAGNOSTICS
def test_transaction_freshness_separates_provider_and_cache_latency():
    from datetime import datetime, timezone
    from application.solana_discovery_token_service import _transaction_freshness

    payload = {
        "as_of": "2026-08-26T04:00:50+00:00",
        "transactions": [{"id": "trade-1", "timestamp": "2026-08-26T04:00:00Z"}],
    }

    result = _transaction_freshness(
        payload,
        served_at=datetime(2026, 8, 26, 4, 1, 0, tzinfo=timezone.utc),
        cache_hit=True,
        stale=False,
    )

    # TRANSACTIONS_FEED_V141_FRESHNESS_SEMANTICS_FIX
    assert result["last_trade_age_seconds"] == 60.0
    assert result["api_age_seconds"] == 10.0
    assert "provider_lag_seconds" not in result
    assert result["cache_hit"] is True
    assert result["stale"] is False


def test_transaction_freshness_handles_missing_trade_without_fabrication():
    from datetime import datetime, timezone
    from application.solana_discovery_token_service import _transaction_freshness

    result = _transaction_freshness(
        {"as_of": "2026-08-26T04:00:50+00:00", "transactions": []},
        served_at=datetime(2026, 8, 26, 4, 1, 0, tzinfo=timezone.utc),
        cache_hit=False,
        stale=False,
    )

    assert result["latest_trade_at"] is None
    assert result["last_trade_age_seconds"] is None
    assert result["api_age_seconds"] == 10.0
    assert "provider_lag_seconds" not in result



# TOKEN_WORKSPACE_V2452_PAIR_AGE_PROPAGATION_FIX
def test_live_pair_age_uses_exact_pair_created_at_without_resetting_to_now():
    from datetime import datetime, timezone
    from application.solana_discovery_token_service import _live_pair_age

    now = datetime(2026, 8, 26, 8, 15, 34, tzinfo=timezone.utc)
    created_ms = 1787728595000  # 2026-08-26T07:16:35Z

    label, hours = _live_pair_age(created_ms, now=now)

    assert label == "58m"
    assert hours is not None
    assert 58 / 60 <= hours < 59 / 60


def test_live_token_detail_overrides_stale_age_with_exact_live_pair_created_at():
    from datetime import datetime, timezone

    observed_now = datetime.now(timezone.utc)
    created_ms = int((observed_now.timestamp() - (58 * 60)) * 1000)

    feed = {
        "updated_label": "Just now",
        "candidates": [{
            "token_address": TOKEN,
            "pair_address": POOL,
            "symbol": "TEST",
            "name": "Test Token",
            "price_usd": 0.1,
            "liquidity_usd": 6000,
            "volume_24h_usd": 2000,
            "pair_age": "<1m",
            "pair_age_hours": 0.0,
        }],
    }

    def get(url, **kwargs):
        if "dexscreener" in url:
            return Response({"pairs": [{
                "pairAddress": POOL,
                "baseToken": {"address": TOKEN},
                "priceUsd": "0.12",
                "liquidity": {"usd": 7000},
                "volume": {"h24": 3000},
                "priceChange": {"h24": 4.5},
                "marketCap": 120000,
                "dexId": "raydium",
                "url": "https://dexscreener.com/solana/pool",
                "pairCreatedAt": created_ms,
            }]})
        return Response({"data": {"attributes": {"ohlcv_list": []}}})

    result = load_solana_discovery_token(TOKEN, feed=feed, request_get=get)

    assert result is not None
    assert result["quote_status"] == "LIVE"
    assert result["pair_age"] == "58m"
    assert result["pair_age_hours"] is not None
    assert 58 / 60 <= result["pair_age_hours"] < 59 / 60


def test_live_token_detail_keeps_stored_age_when_live_pair_created_at_missing():
    feed = {
        "updated_label": "Just now",
        "candidates": [{
            "token_address": TOKEN,
            "pair_address": POOL,
            "symbol": "TEST",
            "name": "Test Token",
            "price_usd": 0.1,
            "liquidity_usd": 6000,
            "volume_24h_usd": 2000,
            "pair_age": "52m",
            "pair_age_hours": 52 / 60,
        }],
    }

    def get(url, **kwargs):
        if "dexscreener" in url:
            return Response({"pairs": [{
                "pairAddress": POOL,
                "baseToken": {"address": TOKEN},
                "priceUsd": "0.12",
                "liquidity": {"usd": 7000},
                "volume": {"h24": 3000},
                "priceChange": {"h24": 4.5},
                "dexId": "raydium",
                "url": "https://dexscreener.com/solana/pool",
            }]})
        return Response({"data": {"attributes": {"ohlcv_list": []}}})

    result = load_solana_discovery_token(TOKEN, feed=feed, request_get=get)

    assert result is not None
    assert result["pair_age"] == "52m"
    assert abs(result["pair_age_hours"] - (52 / 60)) < 1e-9


# TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI
def test_market_activity_normalizes_exact_pool_aggregate():
    from application.solana_discovery_token_service import _normalize_market_activity
    payload={"data":{"id":"solana_"+POOL,"attributes":{"address":POOL,"transactions":{"m5":{"buys":8,"sells":2,"buyers":6,"sellers":2}},"volume_usd":{"m5":"1200.5"}}}}
    result=_normalize_market_activity(payload,POOL)
    assert result["windows"]["m5"]["total_transactions"]==10
    assert result["windows"]["m5"]["buy_percent"]==80.0
    assert result["windows"]["m5"]["buyers"]==6
    assert result["windows"]["m5"]["volume_usd"]==1200.5

def test_market_activity_rejects_wrong_pool_payload():
    from application.solana_discovery_token_service import _normalize_market_activity
    assert _normalize_market_activity({"data":{"id":"solana_WRONG","attributes":{"address":"WRONG"}}},POOL)=={}


def _tw_sec_004_pair_payload(pair_address="pair-cache", token_address="token-cache", price="1.23"):
    return {
        "pairs": [{
            "pairAddress": pair_address,
            "baseToken": {"address": token_address},
            "priceUsd": price,
        }]
    }


def _tw_sec_004_clear_cache():
    with token_service._LIVE_PAIR_LOCK:
        token_service._LIVE_PAIR_CACHE.clear()
        for event in token_service._LIVE_PAIR_INFLIGHT.values():
            event.set()
        token_service._LIVE_PAIR_INFLIGHT.clear()


def test_tw_sec_004_fresh_live_pair_cache_avoids_duplicate_provider_call():
    _tw_sec_004_clear_cache()
    candidate = {"pair_address": "pair-cache", "token_address": "token-cache"}
    calls = 0

    def fake_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return Response(_tw_sec_004_pair_payload())

    with patch.object(token_service.requests, "get", side_effect=fake_get):
        first = token_service._cached_live_pair(candidate, token_service.requests.get)
        second = token_service._cached_live_pair(candidate, token_service.requests.get)

    assert first["priceUsd"] == "1.23"
    assert second["priceUsd"] == "1.23"
    assert calls == 1


def test_tw_sec_004_cache_key_isolated_by_pair_and_token():
    _tw_sec_004_clear_cache()
    calls = 0

    def fake_get(url, **kwargs):
        nonlocal calls
        calls += 1
        pair_address = url.rsplit("/", 1)[-1]
        token_address = "token-a" if pair_address == "pair-a" else "token-b"
        return Response(_tw_sec_004_pair_payload(pair_address, token_address))

    with patch.object(token_service.requests, "get", side_effect=fake_get):
        a = token_service._cached_live_pair(
            {"pair_address": "pair-a", "token_address": "token-a"},
            token_service.requests.get,
        )
        b = token_service._cached_live_pair(
            {"pair_address": "pair-b", "token_address": "token-b"},
            token_service.requests.get,
        )

    assert a["pairAddress"] == "pair-a"
    assert b["pairAddress"] == "pair-b"
    assert calls == 2


def test_tw_sec_004_stale_cache_used_only_within_30_seconds_on_provider_failure():
    _tw_sec_004_clear_cache()
    candidate = {"pair_address": "pair-cache", "token_address": "token-cache"}
    clock = {"value": 100.0}
    calls = 0

    def fake_monotonic():
        return clock["value"]

    def fake_get(url, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response(_tw_sec_004_pair_payload())
        raise token_service.requests.RequestException("provider down")

    with patch.object(token_service, "monotonic", side_effect=fake_monotonic), \
         patch.object(token_service.requests, "get", side_effect=fake_get):
        first = token_service._cached_live_pair(candidate, token_service.requests.get)
        clock["value"] = 110.0
        stale = token_service._cached_live_pair(candidate, token_service.requests.get)
        clock["value"] = 131.0
        import pytest
        with pytest.raises(token_service.requests.RequestException):
            token_service._cached_live_pair(candidate, token_service.requests.get)

    assert first["priceUsd"] == "1.23"
    assert stale["priceUsd"] == "1.23"


def test_tw_sec_004_wrong_pair_or_token_is_not_cached():
    _tw_sec_004_clear_cache()
    candidate = {"pair_address": "pair-cache", "token_address": "token-cache"}
    calls = 0

    def fake_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return Response(_tw_sec_004_pair_payload("wrong-pair", "wrong-token"))

    with patch.object(token_service.requests, "get", side_effect=fake_get):
        assert token_service._cached_live_pair(candidate, token_service.requests.get) is None
        assert token_service._cached_live_pair(candidate, token_service.requests.get) is None

    assert calls == 2


def test_tw_sec_004_custom_request_get_bypasses_shared_cache():
    _tw_sec_004_clear_cache()
    candidate = {"pair_address": "pair-cache", "token_address": "token-cache"}
    calls = 0

    def custom_get(url, **kwargs):
        nonlocal calls
        calls += 1
        return Response(_tw_sec_004_pair_payload())

    token_service._cached_live_pair(candidate, custom_get)
    token_service._cached_live_pair(candidate, custom_get)

    assert calls == 2
    assert not token_service._LIVE_PAIR_CACHE


def test_tw_sec_004_live_pair_cache_is_bounded():
    _tw_sec_004_clear_cache()
    clock = {"value": 1000.0}

    def fake_monotonic():
        value = clock["value"]
        clock["value"] += 0.001
        return value

    def fake_get(url, **kwargs):
        pair_address = url.rsplit("/", 1)[-1]
        token_address = pair_address.replace("pair-", "token-")
        return Response(_tw_sec_004_pair_payload(pair_address, token_address))

    with patch.object(token_service, "monotonic", side_effect=fake_monotonic), \
         patch.object(token_service.requests, "get", side_effect=fake_get):
        for index in range(token_service.MAX_LIVE_PAIR_CACHE_ENTRIES + 25):
            result = token_service._cached_live_pair(
                {"pair_address": f"pair-{index}", "token_address": f"token-{index}"},
                token_service.requests.get,
            )
            assert result is not None

    assert len(token_service._LIVE_PAIR_CACHE) <= token_service.MAX_LIVE_PAIR_CACHE_ENTRIES


def test_tw_sec_004_concurrent_same_pair_miss_coalesces_to_one_dexscreener_call():
    _tw_sec_004_clear_cache()
    candidate = {"pair_address": "pair-cache", "token_address": "token-cache"}
    counter_lock = threading.Lock()
    calls = 0

    def fake_get(url, **kwargs):
        nonlocal calls
        with counter_lock:
            calls += 1
        time.sleep(0.05)
        return Response(_tw_sec_004_pair_payload())

    def load_once(_index):
        return token_service._cached_live_pair(candidate, token_service.requests.get)

    with patch.object(token_service.requests, "get", side_effect=fake_get):
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(load_once, range(20)))

    assert all(result is not None and result["priceUsd"] == "1.23" for result in results)
    assert calls == 1
    assert not token_service._LIVE_PAIR_INFLIGHT

# TW-SEC-008 bounded cache hardening
def test_tw_sec_008_ohlcv_stale_cache_rejected_after_five_minutes(monkeypatch):
    import pytest
    import requests
    import application.solana_discovery_token_service as service

    candidate = {"pair_address": "too-old-pair", "token_address": "too-old-token"}
    with service._OHLCV_CACHE_LOCK:
        service._OHLCV_CACHE.clear()
        service._OHLCV_CACHE[("too-old-pair", "too-old-token", "minute")] = (
            service.monotonic() - (service.OHLCV_STALE_SECONDS + 1.0),
            [{"time": 1.0, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}],
        )

    def failing_provider(candidate, request_get):
        raise requests.RequestException("provider down")

    monkeypatch.setattr(service, "_minute_candles_provider", failing_provider)

    with pytest.raises(requests.RequestException):
        service._minute_candles(candidate, requests.get)


def test_tw_sec_008_transaction_stale_cache_rejected_after_two_minutes(monkeypatch):
    import pytest
    import requests
    import application.solana_discovery_token_service as service

    token = "TooOldTransactionToken"
    with service._TRANSACTION_CACHE_LOCK:
        service._TRANSACTION_CACHE.clear()
        service._TRANSACTION_CACHE[token] = (
            service.monotonic() - (service.TRANSACTION_STALE_SECONDS + 1.0),
            {"token_address": token, "pair_address": "pool", "transactions": [], "as_of": "2026-08-26T00:00:00+00:00", "source": "test"},
        )

    def failing_provider(*args, **kwargs):
        raise requests.RequestException("provider down")

    monkeypatch.setattr(service, "_load_solana_discovery_transactions_provider", failing_provider)

    with pytest.raises(requests.RequestException):
        service.load_solana_discovery_transactions(token)


def test_tw_sec_008_ohlcv_cache_is_bounded_oldest_first():
    import application.solana_discovery_token_service as service

    now = service.monotonic()
    with service._OHLCV_CACHE_LOCK:
        service._OHLCV_CACHE.clear()
        for index in range(305):
            service._OHLCV_CACHE[(f"pair-{index}", f"token-{index}", "minute")] = (
                now - (305 - index) * 0.01,
                [],
            )
        service._prune_ohlcv_cache(now)
        assert len(service._OHLCV_CACHE) == 300
        assert ("pair-0", "token-0", "minute") not in service._OHLCV_CACHE
        assert ("pair-304", "token-304", "minute") in service._OHLCV_CACHE


def test_tw_sec_008_transaction_cache_is_bounded_oldest_first():
    import application.solana_discovery_token_service as service

    now = service.monotonic()
    with service._TRANSACTION_CACHE_LOCK:
        service._TRANSACTION_CACHE.clear()
        for index in range(305):
            service._TRANSACTION_CACHE[f"token-{index}"] = (
                now - (305 - index) * 0.01,
                {"token_address": f"token-{index}", "transactions": []},
            )
        service._prune_transaction_cache(now)
        assert len(service._TRANSACTION_CACHE) == 300
        assert "token-0" not in service._TRANSACTION_CACHE
        assert "token-304" in service._TRANSACTION_CACHE


def test_tw_sec_008_policy_and_tw_sec_004_invariants():
    import application.solana_discovery_token_service as service

    assert service.MAX_OHLCV_CACHE_ENTRIES == 300
    assert service.OHLCV_STALE_SECONDS == 300.0
    assert service.MAX_TRANSACTION_CACHE_ENTRIES == 300
    assert service.TRANSACTION_STALE_SECONDS == 120.0
    assert service.MAX_LIVE_PAIR_CACHE_ENTRIES == 500
    assert service.LIVE_PAIR_STALE_SECONDS == 30.0
    assert service.LIVE_PAIR_TTL_SECONDS == 5.0
