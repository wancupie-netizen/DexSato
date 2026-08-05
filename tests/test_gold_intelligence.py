"""Tests for objective XAU/USD reference intelligence."""

from scanner.gold_intelligence import build_gold_reference_intelligence


def test_should_describe_gold_in_upper_daily_range():
    result = build_gold_reference_intelligence(
        {
            "open": "4000",
            "high": "4100",
            "low": "3950",
            "close": "4080",
            "previous_close": "4020",
        }
    )

    assert result["market_state"] == "UPPER_RANGE"
    assert result["daily_change_pct"] == 1.4925
    assert result["intraday_range_pct"] == 3.75
    assert result["range_position_pct"] == 86.67
    assert "ABOVE_OPEN" in result["evidence"]
    assert "not a trade signal" in result["summary"]


def test_should_collect_data_when_ohlc_is_incomplete():
    result = build_gold_reference_intelligence(
        {"close": "4080"}
    )

    assert result["market_state"] == "COLLECTING_DATA"
    assert result["daily_change_pct"] is None
    assert result["evidence"] == []
