"""On-demand exact-pool OHLCV chart data for DexSato market workspaces."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any

from scanner.http_reliability import request_with_bounded_retry
from scanner.market_registry import get_market


GECKOTERMINAL_OHLCV_URL = (
    "https://api.geckoterminal.com/api/v2/networks/"
    "{network}/pools/{pool_address}/ohlcv/{unit}"
)
CHART_TOKENS = frozenset({"BTC", "ETH", "SOL", "XRP", "SUI"})
TIMEFRAMES = {
    "1h": {"unit": "hour", "aggregate": 1, "limit": 168},
    "4h": {"unit": "hour", "aggregate": 4, "limit": 180},
    "1d": {"unit": "day", "aggregate": 1, "limit": 180},
    "1w": {"unit": "day", "aggregate": 1, "limit": 365},
}
NETWORK_IDS = {
    "bsc": "bsc",
    "ethereum": "eth",
    "solana": "solana",
    "sui": "sui-network",
}
CACHE_SECONDS = 60.0
_CACHE: dict[tuple[str, str], tuple[float, dict[str, object]]] = {}
_CACHE_LOCK = Lock()


class MarketChartUnavailable(RuntimeError):
    """Raised when an allowlisted chart provider cannot serve valid candles."""


def _number(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid OHLCV numbers.")
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("Chart OHLCV contains an invalid number.") from error


def normalize_chart_candles(payload: object) -> list[dict[str, float | int]]:
    """Validate provider candles, sort ascending and remove duplicates."""
    if not isinstance(payload, dict):
        raise ValueError("Chart response must be an object.")
    data = payload.get("data")
    attributes = data.get("attributes") if isinstance(data, dict) else None
    rows = attributes.get("ohlcv_list") if isinstance(attributes, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Chart response does not contain OHLCV candles.")

    candles: dict[int, dict[str, float | int]] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            raise ValueError("Chart candle must contain timestamp and OHLCV.")
        timestamp = int(_number(row[0]))
        candle = {
            "time": timestamp,
            "open": _number(row[1]),
            "high": _number(row[2]),
            "low": _number(row[3]),
            "close": _number(row[4]),
            "volume": _number(row[5]),
        }
        if candle["high"] < candle["low"] or candle["volume"] < 0:
            raise ValueError("Chart candle contains impossible values.")
        candles[timestamp] = candle
    return [candles[key] for key in sorted(candles)]


def aggregate_weekly_candles(
    candles: list[dict[str, float | int]],
) -> list[dict[str, float | int]]:
    """Aggregate UTC daily candles into ISO-week candles."""
    weeks: dict[tuple[int, int], dict[str, float | int]] = {}
    for candle in candles:
        point = datetime.fromtimestamp(int(candle["time"]), timezone.utc)
        iso = point.isocalendar()
        key = (iso.year, iso.week)
        if key not in weeks:
            weeks[key] = dict(candle)
            continue
        current = weeks[key]
        current["high"] = max(float(current["high"]), float(candle["high"]))
        current["low"] = min(float(current["low"]), float(candle["low"]))
        current["close"] = float(candle["close"])
        current["volume"] = float(current["volume"]) + float(candle["volume"])
    return [weeks[key] for key in sorted(weeks)]


def clear_market_chart_cache() -> None:
    """Clear the bounded in-memory cache (primarily for tests)."""
    with _CACHE_LOCK:
        _CACHE.clear()


def fetch_market_chart(
    token: str,
    timeframe: str = "4h",
    *,
    request_get: Callable[..., Any] | None = None,
    now: Callable[[], float] = monotonic,
) -> dict[str, object]:
    """Fetch one allowlisted exact-pool series without affecting decisions."""
    normalized_token = str(token).strip().upper()
    normalized_timeframe = str(timeframe).strip().lower()
    if normalized_token not in CHART_TOKENS:
        raise ValueError("Chart is not available for this market.")
    if normalized_timeframe not in TIMEFRAMES:
        raise ValueError("Unsupported chart timeframe.")

    cache_key = (normalized_token, normalized_timeframe)
    current = now()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached is not None and current - cached[0] < CACHE_SECONDS:
            return dict(cached[1])

    if request_get is None:
        import requests

        request_get = requests.get

    market = get_market(normalized_token)
    network = NETWORK_IDS.get(str(market["chain_id"]).lower())
    if network is None:
        raise ValueError("Chart network is not supported.")
    config = TIMEFRAMES[normalized_timeframe]
    url = GECKOTERMINAL_OHLCV_URL.format(
        network=network,
        pool_address=market["pair_address"],
        unit=config["unit"],
    )

    try:
        response = request_with_bounded_retry(
            lambda: request_get(
                url,
                params={
                    "aggregate": config["aggregate"],
                    "limit": config["limit"],
                    "currency": "usd",
                    # GeckoTerminal rejects SUI Move-type addresses; SUI is
                    # the quote-side asset in this registered exact pool.
                    "token": (
                        "quote"
                        if str(market["chain_id"]).lower() == "sui"
                        else market["base_address"]
                    ),
                },
                headers={"Accept": "application/json"},
                timeout=10,
            ),
            provider="GeckoTerminal market chart",
            max_attempts=2,
        )
        response.raise_for_status()
        candles = normalize_chart_candles(response.json())
    except Exception as error:
        raise MarketChartUnavailable(
            "Live market chart is temporarily unavailable."
        ) from error
    if normalized_timeframe == "1w":
        candles = aggregate_weekly_candles(candles)
    if not candles:
        raise MarketChartUnavailable("Chart provider returned no candles.")

    result: dict[str, object] = {
        "status": "AVAILABLE",
        "token": normalized_token,
        "market": market["display_pair"],
        "timeframe": normalized_timeframe.upper(),
        "source": "GeckoTerminal",
        "network": network,
        "pool_address": market["pair_address"],
        "candles": candles,
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "policy": "EXACT_POOL_READ_ONLY_MARKET_CHART",
    }
    with _CACHE_LOCK:
        _CACHE[cache_key] = (current, dict(result))
    return result
