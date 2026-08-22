"""Near-real-time exact-pool quotes for DexSato market workspaces."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any

from scanner.dexscreener import fetch_registered_pair
from scanner.market_registry import get_market


LIVE_QUOTE_TOKENS = frozenset({"BTC", "ETH", "SOL", "XRP", "SUI"})
FRESH_SECONDS = 10.0
STALE_FALLBACK_SECONDS = 60.0
_CACHE: dict[str, tuple[float, dict[str, object]]] = {}
_CACHE_LOCK = Lock()


class LiveMarketQuoteUnavailable(RuntimeError):
    """Raised when no validated current or bounded stale quote is available."""


def _optional_number(value: object) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _required_positive_number(value: object) -> float:
    number = _optional_number(value)
    if number is None or number <= 0:
        raise ValueError("Live quote price must be a positive number.")
    return number


def normalize_live_quote(
    pair: object,
    market: dict[str, object],
    *,
    recorded_at: datetime | None = None,
) -> dict[str, object]:
    """Normalize an already identity-validated DexScreener exact pair."""
    if not isinstance(pair, dict):
        raise ValueError("Live quote response must be an object.")
    change = pair.get("priceChange")
    volume = pair.get("volume")
    liquidity = pair.get("liquidity")
    moment = recorded_at or datetime.now(timezone.utc)
    return {
        "status": "LIVE",
        "token": str(market["token"]),
        "market": str(market["display_pair"]),
        "price_usd": _required_positive_number(pair.get("priceUsd")),
        "price_change_24h": _optional_number(
            change.get("h24") if isinstance(change, dict) else None
        ),
        "volume_24h": _optional_number(
            volume.get("h24") if isinstance(volume, dict) else None
        ),
        "liquidity": _optional_number(
            liquidity.get("usd") if isinstance(liquidity, dict) else None
        ),
        "market_cap": _optional_number(pair.get("marketCap") or pair.get("fdv")),
        "source": "DexScreener",
        "network": str(market["chain_id"]),
        "pool_address": str(market["pair_address"]),
        "as_of": moment.replace(microsecond=0).isoformat(),
        "age_seconds": 0,
        "policy": "EXACT_POOL_INFORMATIONAL_QUOTE",
    }


def clear_live_market_quote_cache() -> None:
    """Clear the bounded in-memory cache (primarily for tests)."""
    with _CACHE_LOCK:
        _CACHE.clear()


def fetch_live_market_quote(
    token: str,
    *,
    request_get: Callable[..., Any] | None = None,
    now: Callable[[], float] = monotonic,
    recorded_at: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Fetch an exact-pool quote without running or mutating a DexSato scan."""
    normalized_token = str(token).strip().upper()
    if normalized_token not in LIVE_QUOTE_TOKENS:
        raise ValueError("Live price is not available for this market.")

    current = now()
    with _CACHE_LOCK:
        cached = _CACHE.get(normalized_token)
        if cached is not None and current - cached[0] < FRESH_SECONDS:
            result = dict(cached[1])
            result["age_seconds"] = max(0, int(current - cached[0]))
            return result

    market = get_market(normalized_token)
    if request_get is None:
        import requests

        request_get = requests.get
    clock = recorded_at or (lambda: datetime.now(timezone.utc))

    try:
        pair = fetch_registered_pair(market, request_get=request_get)
        result = normalize_live_quote(pair, market, recorded_at=clock())
    except Exception as error:
        with _CACHE_LOCK:
            cached = _CACHE.get(normalized_token)
        if cached is not None:
            age = current - cached[0]
            if age <= STALE_FALLBACK_SECONDS:
                stale = dict(cached[1])
                stale["status"] = "STALE"
                stale["age_seconds"] = max(0, int(age))
                return stale
        raise LiveMarketQuoteUnavailable(
            "Exact-pool live price is temporarily unavailable."
        ) from error

    with _CACHE_LOCK:
        _CACHE[normalized_token] = (current, dict(result))
    return result
