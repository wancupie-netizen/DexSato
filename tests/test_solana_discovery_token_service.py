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
        "token": "base",
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
    assert len(calls) == 1
    assert calls[0][0].endswith(f"/networks/solana/pools/{POOL}/trades")
    assert calls[0][1] == {"token": "base"}
    assert calls[0][2] == 10
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
    candidate = {"pair_address": "cache-pair"}

    first = service._minute_candles(candidate, requests.get)
    second = service._minute_candles(candidate, requests.get)

    assert first == second
    assert calls == ["cache-pair"]


def test_provider_resilience_uses_stale_ohlcv_when_refresh_fails(monkeypatch):
    import requests
    import application.solana_discovery_token_service as service

    service._OHLCV_CACHE.clear()
    candidate = {"pair_address": "stale-pair"}
    cached_rows = [{
        "time": 1700000000.0,
        "open": 1.0,
        "high": 1.1,
        "low": 0.9,
        "close": 1.05,
        "volume": 100.0,
    }]
    service._OHLCV_CACHE[("stale-pair", "minute")] = (
        service.monotonic() - 999.0,
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
        service.monotonic() - 999.0,
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
