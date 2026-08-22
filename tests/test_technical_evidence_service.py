"""Tests for deterministic exact-pool technical evidence."""

from datetime import datetime, timezone

import pytest

from application.technical_evidence_service import (
    MINIMUM_CANDLES,
    calculate_ema,
    calculate_rsi,
    calculate_technical_evidence,
    build_technical_outlook,
    fetch_technical_evidence,
    normalize_closed_candles,
)


def _candles(count=210):
    candles = []
    start = 1_700_000_000
    for index in range(count):
        # A deterministic rising series with periodic pullbacks avoids a
        # permanently saturated RSI while preserving a bullish structure.
        close = 100 + (index * 0.25) + ((index % 5) - 2) * 0.4
        candles.append(
            {
                "timestamp": start + (index * 14_400),
                "open": close - 0.2,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000 + index * 3,
            }
        )
    return candles


def test_should_calculate_wilder_rsi_and_standard_ema():
    values = [float(value) for value in range(1, 202)]

    assert calculate_rsi(values) == 100.0
    assert calculate_ema(values, 200) == pytest.approx(101.5)
    assert calculate_ema(values[:49], 50) is None


def test_should_build_auditable_four_hour_evidence():
    result = calculate_technical_evidence(_candles())

    assert result["status"] == "AVAILABLE"
    assert result["timeframe"] == "4H"
    assert result["source"] == "GeckoTerminal"
    assert result["candle_count"] == 210
    assert set(result["metrics"]) == {
        "rsi_14",
        "ema_50",
        "ema_200",
        "relative_volume_20",
        "market_structure",
    }
    assert result["metrics"]["relative_volume_20"]["value"] > 1
    assert result["metrics"]["market_structure"]["state"] in {
        "HIGHER_HIGH_HIGHER_LOW",
        "LOWER_HIGH_LOWER_LOW",
        "MIXED",
    }
    assert result["outlook"]["policy"] == "READ_ONLY_TECHNICAL_CONTEXT"


def _metrics(*, rsi, ema50, ema200, distance50, distance200, volume, structure):
    return {
        "rsi_14": {"value": rsi},
        "ema_50": {
            "value": ema50,
            "price_distance_pct": distance50,
        },
        "ema_200": {
            "value": ema200,
            "price_distance_pct": distance200,
        },
        "relative_volume_20": {"value": volume},
        "market_structure": {"state": structure},
    }


def test_should_build_bullish_confirmation_and_invalidation_rules():
    outlook = build_technical_outlook(
        _metrics(
            rsi=58,
            ema50=105,
            ema200=100,
            distance50=1.8,
            distance200=6.9,
            volume=1.7,
            structure="HIGHER_HIGH_HIGHER_LOW",
        )
    )

    assert outlook["bias"] == "BULLISH_DEVELOPING"
    assert all(item["status"] == "MET" for item in outlook["confirmation"])
    assert all(item["status"] == "CLEAR" for item in outlook["invalidation"])
    assert outlook["confirmation"][0]["actual"] == "+1.80%"
    assert outlook["confirmation"][2]["requirement"] == (
        "Relative volume at least 1.50×"
    )


def test_should_build_bearish_confirmation_and_invalidation_rules():
    outlook = build_technical_outlook(
        _metrics(
            rsi=41,
            ema50=95,
            ema200=100,
            distance50=-1.4,
            distance200=-6.3,
            volume=1.8,
            structure="LOWER_HIGH_LOWER_LOW",
        )
    )

    assert outlook["bias"] == "BEARISH_DEVELOPING"
    assert all(item["status"] == "MET" for item in outlook["confirmation"])
    assert all(item["status"] == "CLEAR" for item in outlook["invalidation"])
    assert outlook["confirmation"][0]["actual"] == "-1.40%"


def test_should_refuse_to_invent_invalidation_for_mixed_evidence():
    outlook = build_technical_outlook(
        _metrics(
            rsi=56,
            ema50=101,
            ema200=100,
            distance50=-0.1,
            distance200=0.2,
            volume=1.0,
            structure="MIXED",
        )
    )

    assert outlook["bias"] == "MIXED"
    assert "No directional 4H thesis" in outlook["summary"]
    assert outlook["bullish_checks"] == 2
    assert outlook["invalidation"] == [
        {
            "label": "Directional thesis not established",
            "status": "NOT_APPLICABLE",
            "actual": "No active thesis",
            "requirement": (
                "Invalidation begins after a directional bias forms"
            ),
        }
    ]


def test_should_report_insufficient_history_without_fabricating_metrics():
    result = calculate_technical_evidence(_candles(MINIMUM_CANDLES - 1))

    assert result == {
        "status": "INSUFFICIENT_DATA",
        "timeframe": "4H",
        "source": "GeckoTerminal",
        "required_candles": 200,
        "available_candles": 199,
        "metrics": {},
    }


def test_should_sort_dedupe_and_exclude_incomplete_candles():
    now = datetime.fromtimestamp(1_700_100_000, timezone.utc)
    closed = [1_700_000_000, 1, 2, 0.5, 1.5, 100]
    incomplete = [1_700_095_000, 1.5, 2, 1, 1.8, 120]
    payload = {
        "data": {
            "attributes": {
                "ohlcv_list": [incomplete, closed, closed],
            }
        }
    }

    candles = normalize_closed_candles(payload, now=now)

    assert len(candles) == 1
    assert candles[0]["timestamp"] == closed[0]


def test_should_fetch_exact_registered_pool_with_four_hour_parameters():
    rows = [
        [
            candle["timestamp"],
            candle["open"],
            candle["high"],
            candle["low"],
            candle["close"],
            candle["volume"],
        ]
        for candle in reversed(_candles())
    ]

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"attributes": {"ohlcv_list": rows}}}

    calls = []

    def fake_get(url, *, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return Response()

    result = fetch_technical_evidence(
        "SOL",
        request_get=fake_get,
        now=datetime.fromtimestamp(1_800_000_000, timezone.utc),
    )

    assert result["status"] == "AVAILABLE"
    assert result["market"] == "SOL/USDT"
    assert result["network"] == "solana"
    assert "/networks/solana/pools/3nMFw" in calls[0][0]
    assert calls[0][1] == {
        "aggregate": 4,
        "limit": 240,
        "currency": "usd",
        "token": "So11111111111111111111111111111111111111112",
    }
    assert calls[0][3] == 15


def test_sui_technical_evidence_requests_registered_quote_side_asset():
    rows = [
        [
            candle["timestamp"],
            candle["open"],
            candle["high"],
            candle["low"],
            candle["close"],
            candle["volume"],
        ]
        for candle in reversed(_candles())
    ]

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"attributes": {"ohlcv_list": rows}}}

    calls = []

    def fake_get(url, *, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return Response()

    result = fetch_technical_evidence(
        "SUI",
        request_get=fake_get,
        now=datetime.fromtimestamp(1_800_000_000, timezone.utc),
    )

    assert result["status"] == "AVAILABLE"
    assert result["market"] == "SUI/USDC"
    assert result["network"] == "sui-network"
    assert "/networks/sui-network/pools/" in calls[0][0]
    assert calls[0][1]["token"] == "quote"
