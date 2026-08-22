from application.market_chart_service import (
    aggregate_weekly_candles,
    clear_market_chart_cache,
    fetch_market_chart,
    normalize_chart_candles,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _payload():
    return {"data": {"attributes": {"ohlcv_list": [
        [1722643200, 11, 14, 10, 13, 120],
        [1722556800, 10, 12, 9, 11, 100],
        [1722556800, 10, 12, 9, 11, 100],
    ]}}}


def test_chart_candles_are_validated_sorted_and_deduplicated():
    candles = normalize_chart_candles(_payload())

    assert len(candles) == 2
    assert candles[0]["time"] == 1722556800
    assert candles[-1]["close"] == 13


def test_weekly_chart_aggregates_daily_ohlcv():
    candles = normalize_chart_candles(_payload())
    weekly = aggregate_weekly_candles(candles)

    assert len(weekly) == 1
    assert weekly[0]["open"] == 10
    assert weekly[0]["high"] == 14
    assert weekly[0]["low"] == 9
    assert weekly[0]["close"] == 13
    assert weekly[0]["volume"] == 220


def test_chart_uses_exact_registered_pool_and_bounded_cache():
    clear_market_chart_cache()
    calls = []

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(_payload())

    first = fetch_market_chart("btc", "4h", request_get=request_get, now=lambda: 10)
    second = fetch_market_chart("BTC", "4H", request_get=request_get, now=lambda: 20)

    assert first["status"] == "AVAILABLE"
    assert first["network"] == "bsc"
    assert "/networks/bsc/pools/" in calls[0][0]
    assert calls[0][0].endswith("/ohlcv/hour")
    assert calls[0][1]["params"]["aggregate"] == 4
    assert second == first
    assert len(calls) == 1


def test_chart_rejects_non_crypto_and_unknown_timeframe():
    clear_market_chart_cache()
    for token, timeframe in (("XAU", "4h"), ("BTC", "5m")):
        try:
            fetch_market_chart(token, timeframe, request_get=lambda *_a, **_k: None)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsupported chart request should fail closed.")
