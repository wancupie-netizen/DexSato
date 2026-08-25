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
