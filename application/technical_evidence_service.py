"""Deterministic technical evidence for registered DexSato markets.

The service reads closed 4-hour OHLCV candles for the exact registered DEX
pool and calculates auditable indicators.  It enriches presentation data only;
it does not change signals, confidence, or the existing Decision Engine.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from scanner.market_registry import get_market


GECKOTERMINAL_OHLCV_URL = (
    "https://api.geckoterminal.com/api/v2/networks/"
    "{network}/pools/{pool_address}/ohlcv/hour"
)
PRIMARY_TIMEFRAME = "4H"
TIMEFRAME_SECONDS = 4 * 60 * 60
MINIMUM_CANDLES = 200

_NETWORK_IDS = {
    "bsc": "bsc",
    "ethereum": "eth",
    "solana": "solana",
    "sui": "sui-network",
}


def _number(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid market numbers.")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("OHLCV contains an invalid number.") from error


def normalize_closed_candles(
    payload: object,
    *,
    now: datetime | None = None,
) -> list[dict[str, float | int]]:
    """Validate provider OHLCV and return ascending, closed 4H candles."""
    if not isinstance(payload, dict):
        raise ValueError("OHLCV response must be an object.")
    data = payload.get("data")
    attributes = data.get("attributes") if isinstance(data, dict) else None
    rows = attributes.get("ohlcv_list") if isinstance(attributes, dict) else None
    if not isinstance(rows, list):
        raise ValueError("OHLCV response does not contain a candle list.")

    resolved_now = now or datetime.now(timezone.utc)
    if resolved_now.tzinfo is None:
        raise ValueError("OHLCV evaluation time must be timezone-aware.")
    now_epoch = int(resolved_now.timestamp())

    candles: dict[int, dict[str, float | int]] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise ValueError("OHLCV candle must contain timestamp and OHLCV.")
        timestamp = int(_number(row[0]))
        if timestamp + TIMEFRAME_SECONDS > now_epoch:
            continue
        candle = {
            "timestamp": timestamp,
            "open": _number(row[1]),
            "high": _number(row[2]),
            "low": _number(row[3]),
            "close": _number(row[4]),
            "volume": _number(row[5]),
        }
        if candle["high"] < candle["low"] or candle["volume"] < 0:
            raise ValueError("OHLCV candle contains impossible values.")
        candles[timestamp] = candle

    return [candles[key] for key in sorted(candles)]


def calculate_ema(values: Sequence[float], period: int) -> float | None:
    """Calculate a standard exponential moving average."""
    if period <= 0:
        raise ValueError("EMA period must be positive.")
    if len(values) < period:
        return None
    seed = sum(values[:period]) / period
    multiplier = 2 / (period + 1)
    ema = seed
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
    return ema


def calculate_rsi(values: Sequence[float], period: int = 14) -> float | None:
    """Calculate Wilder RSI from a series of closing prices."""
    if period <= 0:
        raise ValueError("RSI period must be positive.")
    if len(values) <= period:
        return None
    changes = [current - previous for previous, current in zip(values, values[1:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def _percent_from(value: float, reference: float | None) -> float | None:
    if reference in (None, 0):
        return None
    return ((value - reference) / reference) * 100


def _rsi_state(value: float) -> str:
    if value >= 70:
        return "OVERBOUGHT"
    if value <= 30:
        return "OVERSOLD"
    return "NEUTRAL"


def _market_structure(candles: Sequence[dict[str, float | int]]) -> str:
    if len(candles) < 2:
        return "UNAVAILABLE"
    previous, current = candles[-2], candles[-1]
    higher_high = current["high"] > previous["high"]
    higher_low = current["low"] > previous["low"]
    lower_high = current["high"] < previous["high"]
    lower_low = current["low"] < previous["low"]
    if higher_high and higher_low:
        return "HIGHER_HIGH_HIGHER_LOW"
    if lower_high and lower_low:
        return "LOWER_HIGH_LOWER_LOW"
    return "MIXED"


def calculate_technical_evidence(
    candles: Sequence[dict[str, float | int]],
    *,
    source: str = "GeckoTerminal",
) -> dict[str, object]:
    """Build transparent 4H evidence without issuing a trade decision."""
    if len(candles) < MINIMUM_CANDLES:
        return {
            "status": "INSUFFICIENT_DATA",
            "timeframe": PRIMARY_TIMEFRAME,
            "source": source,
            "required_candles": MINIMUM_CANDLES,
            "available_candles": len(candles),
            "metrics": {},
        }

    closes = [_number(candle["close"]) for candle in candles]
    volumes = [_number(candle["volume"]) for candle in candles]
    current_price = closes[-1]
    rsi_current = calculate_rsi(closes)
    rsi_previous = calculate_rsi(closes[:-1])
    ema_50 = calculate_ema(closes, 50)
    ema_200 = calculate_ema(closes, 200)
    previous_volume_average = sum(volumes[-21:-1]) / 20
    relative_volume = (
        volumes[-1] / previous_volume_average
        if previous_volume_average > 0
        else None
    )
    candle_time = datetime.fromtimestamp(
        int(candles[-1]["timestamp"]) + TIMEFRAME_SECONDS,
        timezone.utc,
    )

    return {
        "status": "AVAILABLE",
        "timeframe": PRIMARY_TIMEFRAME,
        "source": source,
        "candle_count": len(candles),
        "candle_closed_at": (
            candle_time.replace(microsecond=0).isoformat()
        ),
        "metrics": {
            "rsi_14": {
                "value": round(float(rsi_current), 2),
                "previous": round(float(rsi_previous), 2),
                "state": _rsi_state(float(rsi_current)),
                "direction": (
                    "RISING" if rsi_current > rsi_previous
                    else "FALLING" if rsi_current < rsi_previous
                    else "FLAT"
                ),
            },
            "ema_50": {
                "value": round(float(ema_50), 8),
                "price_distance_pct": round(
                    float(_percent_from(current_price, ema_50)), 2
                ),
            },
            "ema_200": {
                "value": round(float(ema_200), 8),
                "price_distance_pct": round(
                    float(_percent_from(current_price, ema_200)), 2
                ),
            },
            "relative_volume_20": {
                "value": (
                    round(relative_volume, 2)
                    if relative_volume is not None
                    else None
                ),
                "current_volume": round(volumes[-1], 2),
                "average_volume": round(previous_volume_average, 2),
            },
            "market_structure": {
                "state": _market_structure(candles),
            },
        },
    }


def fetch_technical_evidence(
    token: str,
    *,
    request_get: Callable[..., Any] | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Fetch exact-pool candles and calculate optional technical evidence."""
    if request_get is None:
        import requests

        request_get = requests.get

    market = get_market(token)
    network = _NETWORK_IDS.get(str(market["chain_id"]).lower())
    if network is None:
        raise ValueError(f"Unsupported OHLCV network: {market['chain_id']}")

    response = request_get(
        GECKOTERMINAL_OHLCV_URL.format(
            network=network,
            pool_address=market["pair_address"],
        ),
        params={
            "aggregate": 4,
            "limit": 240,
            "currency": "usd",
            "token": "base",
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    candles = normalize_closed_candles(response.json(), now=now)
    evidence = calculate_technical_evidence(candles)
    return {
        **evidence,
        "market": market["display_pair"],
        "pool_address": market["pair_address"],
        "network": network,
    }
