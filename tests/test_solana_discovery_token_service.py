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
