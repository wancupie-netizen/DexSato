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


def _metric_value(metrics: dict[str, object], key: str, field: str) -> float:
    metric = metrics.get(key)
    if not isinstance(metric, dict):
        raise ValueError(f"Technical metric is missing: {key}")
    return _number(metric.get(field))


def _condition(
    label: str,
    status: str,
    actual: str,
    requirement: str,
) -> dict[str, str]:
    return {
        "label": label,
        "status": status,
        "actual": actual,
        "requirement": requirement,
    }


def build_technical_outlook(metrics: dict[str, object]) -> dict[str, object]:
    """Build explicit confirmation and invalidation checks from metrics.

    The outlook is descriptive evidence only.  It cannot override the
    Decision Engine decision or confidence.
    """
    if not isinstance(metrics, dict):
        raise ValueError("Technical metrics must be an object.")

    rsi = _metric_value(metrics, "rsi_14", "value")
    ema50 = _metric_value(metrics, "ema_50", "value")
    ema200 = _metric_value(metrics, "ema_200", "value")
    ema50_distance = _metric_value(
        metrics, "ema_50", "price_distance_pct"
    )
    ema200_distance = _metric_value(
        metrics, "ema_200", "price_distance_pct"
    )
    relative_volume = _metric_value(
        metrics, "relative_volume_20", "value"
    )
    structure_metric = metrics.get("market_structure")
    if not isinstance(structure_metric, dict):
        raise ValueError("Technical metric is missing: market_structure")
    structure = str(structure_metric.get("state", "")).upper()

    bullish_checks = sum(
        (
            ema50_distance > 0,
            ema50 > ema200,
            rsi >= 55,
            structure == "HIGHER_HIGH_HIGHER_LOW",
        )
    )
    bearish_checks = sum(
        (
            ema50_distance < 0,
            ema50 < ema200,
            rsi <= 45,
            structure == "LOWER_HIGH_LOWER_LOW",
        )
    )

    price_vs_ema50 = f"{ema50_distance:+.2f}%"
    price_vs_ema200 = f"{ema200_distance:+.2f}%"
    rsi_actual = f"{rsi:.2f}"
    volume_actual = f"{relative_volume:.2f}×"
    structure_actual = structure.replace("_", " ").title()

    if bullish_checks >= 3 and bullish_checks > bearish_checks:
        bias = "BULLISH_DEVELOPING"
        summary = (
            f"Bullish 4H evidence is developing: {bullish_checks}/4 "
            "directional checks are positive. Treat it as unconfirmed "
            "until the conditions below are met."
        )
        confirmation = [
            _condition(
                "Price holds above EMA50",
                "MET" if ema50_distance > 0 else "PENDING",
                price_vs_ema50,
                "4H close above EMA50 (> 0.00%)",
            ),
            _condition(
                "RSI confirms bullish momentum",
                "MET" if 55 <= rsi < 70 else "PENDING",
                rsi_actual,
                "RSI(14) between 55.00 and 69.99",
            ),
            _condition(
                "Volume confirms participation",
                "MET" if relative_volume >= 1.5 else "PENDING",
                volume_actual,
                "Relative volume at least 1.50×",
            ),
            _condition(
                "Price structure remains constructive",
                "MET" if structure == "HIGHER_HIGH_HIGHER_LOW" else "PENDING",
                structure_actual,
                "Higher high and higher low",
            ),
        ]
        invalidation = [
            _condition(
                "4H close falls below EMA50",
                "TRIGGERED" if ema50_distance < 0 else "CLEAR",
                price_vs_ema50,
                "Triggered below 0.00%",
            ),
            _condition(
                "RSI loses momentum support",
                "TRIGGERED" if rsi < 45 else "CLEAR",
                rsi_actual,
                "Triggered below RSI 45.00",
            ),
            _condition(
                "Structure turns lower",
                "TRIGGERED" if structure == "LOWER_HIGH_LOWER_LOW" else "CLEAR",
                structure_actual,
                "Triggered by lower high and lower low",
            ),
        ]
    elif bearish_checks >= 3 and bearish_checks > bullish_checks:
        bias = "BEARISH_DEVELOPING"
        summary = (
            f"Bearish 4H evidence is developing: {bearish_checks}/4 "
            "directional checks are negative. Treat it as unconfirmed "
            "until the conditions below are met."
        )
        confirmation = [
            _condition(
                "Price holds below EMA50",
                "MET" if ema50_distance < 0 else "PENDING",
                price_vs_ema50,
                "4H close below EMA50 (< 0.00%)",
            ),
            _condition(
                "RSI confirms bearish momentum",
                "MET" if 30 < rsi <= 45 else "PENDING",
                rsi_actual,
                "RSI(14) between 30.01 and 45.00",
            ),
            _condition(
                "Volume confirms participation",
                "MET" if relative_volume >= 1.5 else "PENDING",
                volume_actual,
                "Relative volume at least 1.50×",
            ),
            _condition(
                "Price structure remains weak",
                "MET" if structure == "LOWER_HIGH_LOWER_LOW" else "PENDING",
                structure_actual,
                "Lower high and lower low",
            ),
        ]
        invalidation = [
            _condition(
                "4H close recovers above EMA50",
                "TRIGGERED" if ema50_distance > 0 else "CLEAR",
                price_vs_ema50,
                "Triggered above 0.00%",
            ),
            _condition(
                "RSI regains bullish momentum",
                "TRIGGERED" if rsi > 55 else "CLEAR",
                rsi_actual,
                "Triggered above RSI 55.00",
            ),
            _condition(
                "Structure turns higher",
                "TRIGGERED" if structure == "HIGHER_HIGH_HIGHER_LOW" else "CLEAR",
                structure_actual,
                "Triggered by higher high and higher low",
            ),
        ]
    else:
        bias = "MIXED"
        summary = (
            "No directional 4H thesis is confirmed. "
            f"Bullish checks: {bullish_checks}/4; bearish checks: "
            f"{bearish_checks}/4. Wait for price structure, momentum, "
            "and volume to align."
        )
        aligned_ema = (
            (ema50_distance > 0 and ema200_distance > 0 and ema50 > ema200)
            or (
                ema50_distance < 0
                and ema200_distance < 0
                and ema50 < ema200
            )
        )
        confirmation = [
            _condition(
                "EMA trend alignment",
                "MET" if aligned_ema else "PENDING",
                f"EMA50 {price_vs_ema50}; EMA200 {price_vs_ema200}",
                "Price and EMA50 align on one side of EMA200",
            ),
            _condition(
                "Directional RSI zone",
                "MET" if rsi >= 55 or rsi <= 45 else "PENDING",
                rsi_actual,
                "RSI(14) at least 55.00 or at most 45.00",
            ),
            _condition(
                "Volume expansion",
                "MET" if relative_volume >= 1.5 else "PENDING",
                volume_actual,
                "Relative volume at least 1.50×",
            ),
            _condition(
                "Directional market structure",
                "MET" if structure in {
                    "HIGHER_HIGH_HIGHER_LOW",
                    "LOWER_HIGH_LOWER_LOW",
                } else "PENDING",
                structure_actual,
                "Higher-high/higher-low or lower-high/lower-low",
            ),
        ]
        invalidation = [
            _condition(
                "Directional thesis not established",
                "NOT_APPLICABLE",
                "No active thesis",
                "Invalidation begins after a directional bias forms",
            )
        ]

    return {
        "bias": bias,
        "summary": summary,
        "bullish_checks": bullish_checks,
        "bearish_checks": bearish_checks,
        "confirmation": confirmation,
        "invalidation": invalidation,
        "policy": "READ_ONLY_TECHNICAL_CONTEXT",
    }


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

    metrics = {
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
    }

    return {
        "status": "AVAILABLE",
        "timeframe": PRIMARY_TIMEFRAME,
        "source": source,
        "candle_count": len(candles),
        "candle_closed_at": (
            candle_time.replace(microsecond=0).isoformat()
        ),
        "metrics": metrics,
        "outlook": build_technical_outlook(metrics),
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
            "token": market["base_address"],
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
