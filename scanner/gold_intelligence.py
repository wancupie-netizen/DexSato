"""Objective, non-predictive reference intelligence for XAU/USD."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _percent_change(current, previous):
    if current is None or previous in (None, Decimal("0")):
        return None
    return round(float(((current - previous) / previous) * 100), 4)


def build_gold_reference_intelligence(quote: dict) -> dict:
    """Describe the current daily candle without issuing a trade signal."""
    open_price = _decimal(quote.get("open"))
    high = _decimal(quote.get("high"))
    low = _decimal(quote.get("low"))
    close = _decimal(quote.get("close"))
    previous_close = _decimal(quote.get("previous_close"))

    required = (open_price, high, low, close, previous_close)
    if any(value is None for value in required) or high <= low:
        return {
            "market_state": "COLLECTING_DATA",
            "daily_change_pct": None,
            "intraday_range_pct": None,
            "range_position_pct": None,
            "evidence": [],
            "summary": "Gold reference intelligence needs complete OHLC data.",
        }

    daily_change = _percent_change(close, previous_close)
    intraday_range = round(
        float(((high - low) / open_price) * 100),
        4,
    )

    range_position = round(float(((close - low) / (high - low)) * 100), 2)

    if range_position >= 66.67:
        market_state = "UPPER_RANGE"
        range_label = "upper third of today's range"
    elif range_position <= 33.33:
        market_state = "LOWER_RANGE"
        range_label = "lower third of today's range"
    else:
        market_state = "MID_RANGE"
        range_label = "middle third of today's range"

    if close > open_price:
        open_relation = "ABOVE_OPEN"
        open_text = "above the daily open"
    elif close < open_price:
        open_relation = "BELOW_OPEN"
        open_text = "below the daily open"
    else:
        open_relation = "AT_OPEN"
        open_text = "at the daily open"

    evidence = [
        open_relation,
        market_state,
        f"DAILY_CHANGE_{daily_change:+.4f}%",
        f"INTRADAY_RANGE_{intraday_range:.4f}%",
    ]

    summary = (
        f"XAU/USD is {open_text} and in the {range_label}. "
        f"Daily change is {daily_change:+.4f}% with an intraday "
        f"range of {intraday_range:.4f}%. This is reference "
        "intelligence, not a trade signal."
    )

    return {
        "market_state": market_state,
        "daily_change_pct": daily_change,
        "intraday_range_pct": intraday_range,
        "range_position_pct": range_position,
        "evidence": evidence,
        "summary": summary,
    }
