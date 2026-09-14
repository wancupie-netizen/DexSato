"""Exact-token read model for the Solana Discovery D4 workspace."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import threading
from time import monotonic
from typing import Any, Callable

import requests

from application.solana_discovery_feed_service import load_solana_discovery_feed, load_solana_discovery_record


DEXSCREENER_PAIR_URL = "https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# TRANSACTIONS_FEED_V10_EXACT_POOL_SERVICE
GECKO_TRADES_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/"
    "{pair_address}/trades"
)
# TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI
GECKO_POOL_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/"
    "{pair_address}"
)
MARKET_ACTIVITY_WINDOWS = ("m5", "m15", "m30", "h1", "h6", "h24")
GECKO_OHLCV_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/"
    "{pair_address}/ohlcv/hour"
)

# TOKEN_WORKSPACE_V25_MULTITIMEFRAME_CANDLESTICK
GECKO_HOURLY_OHLCV_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/"
    "{pair_address}/ohlcv/hour"
)

# TOKEN_WORKSPACE_V23_REAL_TIMEFRAME_INTELLIGENCE
GECKO_MINUTE_OHLCV_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/"
    "{pair_address}/ohlcv/minute"
)

# TW-DATA-01A_EXACT_POOL_FALLBACK
BIRDEYE_OHLCV_PAIR_URL = "https://public-api.birdeye.so/defi/ohlcv/pair"
BIRDEYE_TRADES_PAIR_URL = "https://public-api.birdeye.so/defi/txs/pair"
BIRDEYE_OHLCV_SECONDS = {"1m": 60, "1H": 3600, "4H": 14400}
TRADER_TIMEFRAME_MINUTES = {
    "change_1m": 1,
    "change_5m": 5,
    "change_15m": 15,
    "change_30m": 30,
    "change_1h": 60,
    "change_4h": 240,
}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# TW_DEX_03J1_EXACT_TARGET_OHLCV
def _normalize_ohlcv_rows(rows: Any) -> list[dict[str, float]]:
    """Return valid provider candles in ascending order, one per timestamp."""
    if not isinstance(rows, list):
        return []

    candles_by_time: dict[float, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        values = [_number(value) for value in row[:6]]
        if any(value is None or not math.isfinite(value) for value in values):
            continue

        timestamp, open_value, high_value, low_value, close_value, volume = (
            float(value) for value in values if value is not None
        )
        if (
            timestamp <= 0
            or min(open_value, high_value, low_value, close_value) <= 0
            or volume < 0
            or high_value < max(open_value, close_value)
            or low_value > min(open_value, close_value)
        ):
            continue

        # GeckoTerminal normally returns newest first. When a timestamp is
        # repeated, retain the provider's first row deterministically.
        candles_by_time.setdefault(timestamp, {
            "time": timestamp,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "close": close_value,
            "volume": volume,
        })

    return [candles_by_time[timestamp] for timestamp in sorted(candles_by_time)]


def _birdeye_api_key() -> str:
    """Return the server-side provider key without ever exposing it downstream."""
    return os.getenv("BIRDEYE_API_KEY", "").strip()


def _normalize_birdeye_ohlcv(payload: Any) -> list[dict[str, float]]:
    """Translate Birdeye pair candles into the existing strict candle contract."""
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return []
    data = payload.get("data")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    rows: list[list[Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append([
            item.get("unixTime", item.get("unix_time")),
            item.get("o", item.get("open")),
            item.get("h", item.get("high")),
            item.get("l", item.get("low")),
            item.get("c", item.get("close")),
            item.get("v", item.get("volume")),
        ])
    return _normalize_ohlcv_rows(rows)


def _birdeye_ohlcv_provider(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
    *,
    timeframe: str,
    limit: int,
) -> list[dict[str, float]]:
    """Read exact-pair OHLCV only when the configured fallback is available."""
    pair_address = str(candidate.get("pair_address") or "")
    api_key = _birdeye_api_key()
    seconds = BIRDEYE_OHLCV_SECONDS.get(timeframe)
    if not pair_address or not api_key or seconds is None:
        return []

    time_to = int(datetime.now(timezone.utc).timestamp())
    time_from = max(1, time_to - (seconds * max(2, limit + 2)))
    response = request_get(
        BIRDEYE_OHLCV_PAIR_URL,
        params={
            "address": pair_address,
            "type": timeframe,
            "time_from": time_from,
            "time_to": time_to,
        },
        headers={"X-API-KEY": api_key, "x-chain": "solana"},
        timeout=10,
    )
    response.raise_for_status()
    return _normalize_birdeye_ohlcv(response.json())[-limit:]


# TOKEN_OBSERVATION_V28_ONCHAIN_AUTHORITY
def _mint_authorities(token_address: str, request_post: Callable[..., Any]) -> dict[str, str]:
    """Read only authority facts exposed by the parsed Solana mint account."""
    result = {
        "mint_authority_observation": "Unavailable",
        "freeze_authority_observation": "Unavailable",
        "metadata_observation": "Unavailable",
    }
    endpoint = (os.getenv("SOLANA_RPC_URL", "") or SOLANA_RPC_URL).strip()
    try:
        response = request_post(
            endpoint,
            json={"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo",
                  "params": [token_address, {"encoding": "jsonParsed"}]},
            headers={"accept": "application/json", "content-type": "application/json"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        value = payload.get("result", {}).get("value") if isinstance(payload, dict) else None
        data = value.get("data") if isinstance(value, dict) else None
        parsed = data.get("parsed") if isinstance(data, dict) else None
        info = parsed.get("info") if isinstance(parsed, dict) else None
        if not isinstance(info, dict):
            return result
        result["mint_authority_observation"] = "Revoked" if info.get("mintAuthority") is None else "Active"
        result["freeze_authority_observation"] = "Revoked" if info.get("freezeAuthority") is None else "Active"
    except (requests.RequestException, RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return result


# TOKEN_WORKSPACE_V2452_PAIR_AGE_PROPAGATION_FIX
def _live_pair_age(created_at: Any, *, now: datetime | None = None) -> tuple[str, float | None]:
    current = now or datetime.now(timezone.utc)
    try:
        created = datetime.fromtimestamp(float(created_at) / 1000, tz=timezone.utc)
        seconds = max(0.0, (current - created).total_seconds())
    except (TypeError, ValueError, OSError, OverflowError):
        return "Unavailable", None

    hours = seconds / 3600.0
    total_minutes = max(0, int(seconds // 60))

    if total_minutes < 1:
        label = "<1m"
    elif total_minutes < 60:
        label = f"{total_minutes}m"
    else:
        total_hours, minutes = divmod(total_minutes, 60)
        if total_hours < 24:
            label = f"{total_hours}h {minutes}m" if minutes else f"{total_hours}h"
        else:
            days, hours_left = divmod(total_hours, 24)
            label = f"{days}d {hours_left}h" if hours_left else f"{days}d"

    return label, hours


def _live_pair_provider(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> dict[str, Any] | None:
    pair_address = str(candidate.get("pair_address") or "")
    token_address = str(candidate.get("token_address") or "")
    if not pair_address or not token_address:
        return None
    response = request_get(DEXSCREENER_PAIR_URL.format(pair_address=pair_address), timeout=10)
    response.raise_for_status()
    payload = response.json()
    pairs = payload.get("pairs") if isinstance(payload, dict) else None
    if not isinstance(pairs, list):
        return None
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        if str(pair.get("pairAddress") or "") != pair_address:
            continue
        base = pair.get("baseToken") if isinstance(pair.get("baseToken"), dict) else {}
        if str(base.get("address") or "") != token_address:
            continue
        return pair
    return None


LIVE_PAIR_TTL_SECONDS = 5.0
LIVE_PAIR_STALE_SECONDS = 30.0
MAX_LIVE_PAIR_CACHE_ENTRIES = 500

_LIVE_PAIR_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_LIVE_PAIR_INFLIGHT: dict[tuple[str, str], threading.Event] = {}
_LIVE_PAIR_LOCK = threading.RLock()


def _copy_live_pair(pair: dict[str, Any]) -> dict[str, Any]:
    return dict(pair)


def _prune_live_pair_cache(now: float) -> None:
    stale_keys = [
        key
        for key, (stored_at, _pair) in _LIVE_PAIR_CACHE.items()
        if (now - stored_at) > LIVE_PAIR_STALE_SECONDS
    ]
    for key in stale_keys:
        _LIVE_PAIR_CACHE.pop(key, None)

    if len(_LIVE_PAIR_CACHE) <= MAX_LIVE_PAIR_CACHE_ENTRIES:
        return

    oldest = sorted(_LIVE_PAIR_CACHE.items(), key=lambda item: item[1][0])
    remove_count = len(_LIVE_PAIR_CACHE) - MAX_LIVE_PAIR_CACHE_ENTRIES
    for key, _value in oldest[:remove_count]:
        _LIVE_PAIR_CACHE.pop(key, None)


def _cached_live_pair(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> dict[str, Any] | None:
    """Coalesce production DexScreener reads and use bounded stale fallback."""
    if request_get is not requests.get:
        return _live_pair_provider(candidate, request_get)

    pair_address = str(candidate.get("pair_address") or "")
    token_address = str(candidate.get("token_address") or "")
    if not pair_address or not token_address:
        return None

    key = (pair_address, token_address)
    now_value = monotonic()

    with _LIVE_PAIR_LOCK:
        _prune_live_pair_cache(now_value)
        cached = _LIVE_PAIR_CACHE.get(key)
        if cached is not None and (now_value - cached[0]) < LIVE_PAIR_TTL_SECONDS:
            return _copy_live_pair(cached[1])

        event = _LIVE_PAIR_INFLIGHT.get(key)
        if event is None:
            event = threading.Event()
            _LIVE_PAIR_INFLIGHT[key] = event
            refresher = True
        else:
            refresher = False

    if not refresher:
        event.wait(timeout=10.5)
        current = monotonic()
        with _LIVE_PAIR_LOCK:
            cached = _LIVE_PAIR_CACHE.get(key)
            if cached is not None and (current - cached[0]) <= LIVE_PAIR_STALE_SECONDS:
                return _copy_live_pair(cached[1])
        return None

    try:
        pair = _live_pair_provider(candidate, request_get)
        current = monotonic()
        with _LIVE_PAIR_LOCK:
            if pair is not None:
                _LIVE_PAIR_CACHE[key] = (current, _copy_live_pair(pair))
                _prune_live_pair_cache(current)
                return _copy_live_pair(pair)

            cached = _LIVE_PAIR_CACHE.get(key)
            if cached is not None and (current - cached[0]) <= LIVE_PAIR_STALE_SECONDS:
                return _copy_live_pair(cached[1])
            return None
    except (requests.RequestException, RuntimeError, ValueError, TypeError):
        current = monotonic()
        with _LIVE_PAIR_LOCK:
            cached = _LIVE_PAIR_CACHE.get(key)
            if cached is not None and (current - cached[0]) <= LIVE_PAIR_STALE_SECONDS:
                return _copy_live_pair(cached[1])
        raise
    finally:
        with _LIVE_PAIR_LOCK:
            completed = _LIVE_PAIR_INFLIGHT.pop(key, None)
            if completed is not None:
                completed.set()


def _live_pair(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> dict[str, Any] | None:
    return _cached_live_pair(candidate, request_get)


def _chart_provider(candidate: dict[str, Any], request_get: Callable[..., Any]) -> list[dict[str, float]]:
    pair_address = str(candidate.get("pair_address") or "")
    token_address = str(candidate.get("token_address") or "")
    if not pair_address or not token_address:
        return []
    response = request_get(
        GECKO_OHLCV_URL.format(pair_address=pair_address),
        params={"aggregate": 4, "limit": 90, "currency": "usd", "token": token_address},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    attributes = data.get("attributes") if isinstance(data, dict) else None
    rows = attributes.get("ohlcv_list") if isinstance(attributes, dict) else None
    primary = _normalize_ohlcv_rows(rows)
    if primary:
        return primary
    try:
        return _birdeye_ohlcv_provider(
            candidate, request_get, timeframe="4H", limit=90,
        )
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return []



def _minute_candles_provider(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> list[dict[str, float]]:
    pair_address = str(candidate.get("pair_address") or "")
    token_address = str(candidate.get("token_address") or "")
    if not pair_address or not token_address:
        return []
    response = request_get(
        GECKO_MINUTE_OHLCV_URL.format(pair_address=pair_address),
        params={
            "aggregate": 1,
            "limit": 300,
            "currency": "usd",
            "token": token_address,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    attributes = data.get("attributes") if isinstance(data, dict) else None
    rows = attributes.get("ohlcv_list") if isinstance(attributes, dict) else None
    primary = _normalize_ohlcv_rows(rows)
    if primary:
        return primary
    try:
        return _birdeye_ohlcv_provider(
            candidate, request_get, timeframe="1m", limit=300,
        )
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return []


def _change_between(newer: float, older: float) -> float | None:
    if older <= 0:
        return None
    return ((newer / older) - 1.0) * 100.0


def _trader_timeframe_changes(
    candles: list[dict[str, float]],
) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        key: None for key in TRADER_TIMEFRAME_MINUTES
    }
    if not candles:
        return result

    newest_time = _number(candles[-1].get("time"))
    newest_close = _number(candles[-1].get("close"))
    if newest_time is None or newest_close is None:
        return result

    for key, minutes in TRADER_TIMEFRAME_MINUTES.items():
        target = newest_time - (minutes * 60)
        eligible = []
        for candle in candles:
            candle_time = _number(candle.get("time"))
            if candle_time is not None and candle_time <= target:
                eligible.append(candle)
        if not eligible:
            continue
        older = max(eligible, key=lambda candle: float(candle["time"]))
        older_close = _number(older.get("close"))
        if older_close is None:
            continue
        result[key] = _change_between(newest_close, older_close)

    return result



def _aggregate_candles(
    candles: list[dict[str, float]],
    minutes: int,
) -> list[dict[str, float]]:
    if minutes <= 1:
        return list(candles)

    bucket_seconds = minutes * 60
    buckets: dict[int, list[dict[str, float]]] = {}
    for candle in candles:
        timestamp = _number(candle.get("time"))
        if timestamp is None:
            continue
        bucket = int(timestamp // bucket_seconds) * bucket_seconds
        buckets.setdefault(bucket, []).append(candle)

    result: list[dict[str, float]] = []
    for bucket in sorted(buckets):
        rows = sorted(buckets[bucket], key=lambda item: float(item["time"]))
        if not rows:
            continue
        open_value = _number(rows[0].get("open"))
        close_value = _number(rows[-1].get("close"))
        highs = [_number(row.get("high")) for row in rows]
        lows = [_number(row.get("low")) for row in rows]
        volumes = [_number(row.get("volume")) for row in rows]
        if (
            open_value is None
            or close_value is None
            or any(value is None for value in highs)
            or any(value is None for value in lows)
            or any(value is None for value in volumes)
        ):
            continue
        result.append({
            "time": float(bucket),
            "open": open_value,
            "high": max(float(value) for value in highs if value is not None),
            "low": min(float(value) for value in lows if value is not None),
            "close": close_value,
            "volume": sum(float(value) for value in volumes if value is not None),
        })
    return result


def _hourly_candles_provider(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> list[dict[str, float]]:
    pair_address = str(candidate.get("pair_address") or "")
    token_address = str(candidate.get("token_address") or "")
    if not pair_address or not token_address:
        return []
    response = request_get(
        GECKO_HOURLY_OHLCV_URL.format(pair_address=pair_address),
        params={
            "aggregate": 1,
            "limit": 120,
            "currency": "usd",
            "token": token_address,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    attributes = data.get("attributes") if isinstance(data, dict) else None
    rows = attributes.get("ohlcv_list") if isinstance(attributes, dict) else None
    primary = _normalize_ohlcv_rows(rows)
    if primary:
        return primary
    try:
        return _birdeye_ohlcv_provider(
            candidate, request_get, timeframe="1H", limit=120,
        )
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return []



# TRANSACTIONS_FEED_V123_PROVIDER_RESILIENCE
_OHLCV_CACHE: dict[tuple[str, str, str], tuple[float, list[dict[str, float]]]] = {}
_TRANSACTION_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

_OHLCV_TTL_SECONDS = {
    "minute": 45.0,
    "hour": 60.0,
    "4h": 60.0,
}
_TRANSACTION_TTL_SECONDS = 20.0

OHLCV_STALE_SECONDS = 300.0
TRANSACTION_STALE_SECONDS = 120.0
MAX_OHLCV_CACHE_ENTRIES = 300
MAX_TRANSACTION_CACHE_ENTRIES = 300

_OHLCV_CACHE_LOCK = threading.RLock()
_TRANSACTION_CACHE_LOCK = threading.RLock()


def _prune_ohlcv_cache(now: float) -> None:
    stale_keys = [
        key
        for key, (stored_at, _rows) in _OHLCV_CACHE.items()
        if (now - stored_at) > OHLCV_STALE_SECONDS
    ]
    for key in stale_keys:
        _OHLCV_CACHE.pop(key, None)

    if len(_OHLCV_CACHE) <= MAX_OHLCV_CACHE_ENTRIES:
        return

    oldest = sorted(_OHLCV_CACHE.items(), key=lambda item: item[1][0])
    remove_count = len(_OHLCV_CACHE) - MAX_OHLCV_CACHE_ENTRIES
    for key, _value in oldest[:remove_count]:
        _OHLCV_CACHE.pop(key, None)


def _prune_transaction_cache(now: float) -> None:
    stale_keys = [
        key
        for key, (stored_at, _payload) in _TRANSACTION_CACHE.items()
        if (now - stored_at) > TRANSACTION_STALE_SECONDS
    ]
    for key in stale_keys:
        _TRANSACTION_CACHE.pop(key, None)

    if len(_TRANSACTION_CACHE) <= MAX_TRANSACTION_CACHE_ENTRIES:
        return

    oldest = sorted(_TRANSACTION_CACHE.items(), key=lambda item: item[1][0])
    remove_count = len(_TRANSACTION_CACHE) - MAX_TRANSACTION_CACHE_ENTRIES
    for key, _value in oldest[:remove_count]:
        _TRANSACTION_CACHE.pop(key, None)


def _copy_candles(rows: list[dict[str, float]]) -> list[dict[str, float]]:
    return [dict(row) for row in rows]


def _cached_ohlcv(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
    cache_kind: str,
    provider: Callable[[dict[str, Any], Callable[..., Any]], list[dict[str, float]]],
) -> list[dict[str, float]]:
    if request_get is not requests.get:
        return provider(candidate, request_get)

    pair_address = str(candidate.get("pair_address") or "")
    token_address = str(candidate.get("token_address") or "")
    if not pair_address or not token_address:
        return []

    key = (pair_address, token_address, cache_kind)
    now = monotonic()
    ttl = _OHLCV_TTL_SECONDS[cache_kind]

    with _OHLCV_CACHE_LOCK:
        _prune_ohlcv_cache(now)
        cached = _OHLCV_CACHE.get(key)
        if cached is not None and (now - cached[0]) < ttl:
            return _copy_candles(cached[1])

    try:
        rows = provider(candidate, request_get)
    except requests.RequestException:
        current = monotonic()
        with _OHLCV_CACHE_LOCK:
            _prune_ohlcv_cache(current)
            cached = _OHLCV_CACHE.get(key)
            if cached is not None and (current - cached[0]) <= OHLCV_STALE_SECONDS:
                return _copy_candles(cached[1])
        raise

    current = monotonic()
    copied = _copy_candles(rows)
    with _OHLCV_CACHE_LOCK:
        _OHLCV_CACHE[key] = (current, copied)
        _prune_ohlcv_cache(current)
    return _copy_candles(copied)


def _chart(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> list[dict[str, float]]:
    return _cached_ohlcv(candidate, request_get, "4h", _chart_provider)


def _minute_candles(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> list[dict[str, float]]:
    return _cached_ohlcv(candidate, request_get, "minute", _minute_candles_provider)


def _hourly_candles(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> list[dict[str, float]]:
    return _cached_ohlcv(candidate, request_get, "hour", _hourly_candles_provider)


def _candlestick_timeframes(
    minute_candles: list[dict[str, float]],
    hourly_candles: list[dict[str, float]],
    four_hour_candles: list[dict[str, float]],
) -> dict[str, list[dict[str, float]]]:
    return {
        "1m": minute_candles[-180:],
        "5m": _aggregate_candles(minute_candles, 5)[-120:],
        "15m": _aggregate_candles(minute_candles, 15)[-120:],
        "30m": _aggregate_candles(minute_candles, 30)[-120:],
        "1H": hourly_candles[-120:],
        "4H": four_hour_candles[-90:],
    }



# CHART_V22_LIVE_CANDLE
LIVE_CANDLE_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1H", "4H"}

# CHART_V221_LIVE_CANDLE_BUILDER
LIVE_CANDLE_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "4H": 14400,
}


def _merge_live_price_into_candles(
    candles: list[dict[str, float]],
    timeframe: str,
    live_price: float | None,
    observed_at: float,
) -> tuple[list[dict[str, Any]], bool]:
    # Merge one verified exact-pool price observation into the open candle.
    # Historical OHLCV remains provider-owned. No trade volume is invented.
    if (
        not candles
        or timeframe not in LIVE_CANDLE_SECONDS
        or live_price is None
        or live_price <= 0
    ):
        return [dict(candle) for candle in candles], False

    bucket_seconds = LIVE_CANDLE_SECONDS[timeframe]
    bucket_time = int(float(observed_at) // bucket_seconds) * bucket_seconds
    result: list[dict[str, Any]] = [dict(candle) for candle in candles]

    last_time = _number(result[-1].get("time")) if result else None

    if last_time is not None and int(last_time) == bucket_time:
        candle = result[-1]
        open_value = _number(candle.get("open"))
        high_value = _number(candle.get("high"))
        low_value = _number(candle.get("low"))

        if open_value is None:
            open_value = live_price

        candle["open"] = open_value
        candle["high"] = max(value for value in (high_value, live_price) if value is not None)
        candle["low"] = min(value for value in (low_value, live_price) if value is not None)
        candle["close"] = live_price
        candle["live"] = True
        candle["volume_live"] = False
        return result, True

    if last_time is None or int(last_time) < bucket_time:
        result.append({
            "time": float(bucket_time),
            "open": live_price,
            "high": live_price,
            "low": live_price,
            "close": live_price,
            "volume": None,
            "live": True,
            "volume_live": False,
        })
        return result, True

    return result, False


def load_solana_discovery_live_candles(
    token_address: str,
    timeframe: str,
    *,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    address = str(token_address or "").strip()
    selected = str(timeframe or "").strip()

    if not address or len(address) > 80 or "/" in address:
        return None
    if selected not in LIVE_CANDLE_TIMEFRAMES:
        raise ValueError("Unsupported candlestick timeframe.")

    public_feed = feed if feed is not None else load_solana_discovery_feed()
    candidates = public_feed.get("candidates") if isinstance(public_feed, dict) else None
    if not isinstance(candidates, list):
        return None

    candidate = next(
        (
            item
            for item in candidates
            if isinstance(item, dict) and item.get("token_address") == address
        ),
        None,
    )
    if candidate is None:
        return None

    if selected in {"1m", "5m", "15m", "30m"}:
        minute = _minute_candles(candidate, request_get)
        if selected == "1m":
            candles = minute[-180:]
        else:
            minutes = {"5m": 5, "15m": 15, "30m": 30}[selected]
            candles = _aggregate_candles(minute, minutes)[-120:]
    elif selected == "1H":
        candles = _hourly_candles(candidate, request_get)[-120:]
    else:
        candles = _chart(candidate, request_get)[-90:]

    observed_now = datetime.now(timezone.utc)
    live_price = None
    live_observation = False

    try:
        pair = _live_pair(candidate, request_get)
        if pair is not None:
            live_price = _number(pair.get("priceUsd"))
    except (requests.RequestException, RuntimeError, ValueError, TypeError):
        live_price = None

    candles, live_observation = _merge_live_price_into_candles(
        candles,
        selected,
        live_price,
        observed_now.timestamp(),
    )

    return {
        "token_address": address,
        "timeframe": selected,
        "candles": candles,
        "as_of": observed_now.isoformat(),
        "live_price": live_price,
        "live_observation": live_observation,
        "volume_live": False,
    }



# TRANSACTIONS_FEED_V10_EXACT_POOL_SERVICE
def _transaction_candidate(token_address: str, feed: dict[str, Any]) -> dict[str, Any] | None:
    candidates = feed.get("candidates") if isinstance(feed, dict) else None
    if not isinstance(candidates, list):
        return None
    return next(
        (
            item for item in candidates
            if isinstance(item, dict)
            and str(item.get("token_address") or "") == token_address
            and str(item.get("pair_address") or "")
        ),
        None,
    )


def _normalize_exact_pool_trade(row: dict[str, Any], token_address: str) -> dict[str, Any] | None:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    trade_id = str(row.get("id") or "").strip()
    tx_hash = str(attributes.get("tx_hash") or "").strip()
    timestamp = str(attributes.get("block_timestamp") or "").strip()
    trader = str(attributes.get("tx_from_address") or "").strip()
    from_address = str(attributes.get("from_token_address") or "").strip()
    to_address = str(attributes.get("to_token_address") or "").strip()

    if not trade_id or not tx_hash or not timestamp:
        return None

    if to_address == token_address:
        side = "BUY"
        token_amount = _number(attributes.get("to_token_amount"))
        price_usd = _number(attributes.get("price_to_in_usd"))
    elif from_address == token_address:
        side = "SELL"
        token_amount = _number(attributes.get("from_token_amount"))
        price_usd = _number(attributes.get("price_from_in_usd"))
    else:
        return None

    volume_usd = _number(attributes.get("volume_in_usd"))
    if token_amount is None or token_amount < 0:
        return None
    if price_usd is None or price_usd < 0:
        return None
    if volume_usd is None or volume_usd < 0:
        return None

    return {
        "id": trade_id,
        "tx_hash": tx_hash,
        "timestamp": timestamp,
        "trader": trader or None,
        "side": side,
        "price_usd": price_usd,
        "token_amount": token_amount,
        "volume_usd": volume_usd,
    }


def _normalize_exact_pool_trades(payload: Any, token_address: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []

    transactions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = _normalize_exact_pool_trade(row, token_address)
        if normalized is None:
            continue
        identity = str(normalized["id"])
        if identity in seen:
            continue
        seen.add(identity)
        transactions.append(normalized)

    transactions.sort(
        key=lambda item: (str(item.get("timestamp") or ""), str(item.get("id") or "")),
        reverse=True,
    )
    return transactions


def _birdeye_asset_address(asset: Any) -> str:
    if not isinstance(asset, dict):
        return ""
    return str(asset.get("address") or asset.get("mint") or "").strip()


def _birdeye_asset_number(asset: Any, *keys: str) -> float | None:
    if not isinstance(asset, dict):
        return None
    for key in keys:
        value = _number(asset.get(key))
        if value is not None:
            return value
    return None


def _normalize_birdeye_exact_pool_trade(
    row: dict[str, Any], token_address: str, pair_address: str,
) -> dict[str, Any] | None:
    """Fail closed unless the Birdeye row proves both pool and token identity."""
    returned_pool = str(
        row.get("poolId") or row.get("pool_id")
        or row.get("poolAddress") or row.get("pool_address")
        or row.get("address") or ""
    ).strip()
    if returned_pool != pair_address:
        return None

    tx_hash = str(row.get("txHash") or row.get("tx_hash") or "").strip()
    timestamp_value = _number(row.get("blockUnixTime", row.get("block_unix_time")))
    if not tx_hash or timestamp_value is None or timestamp_value <= 0:
        return None

    from_asset = row.get("from")
    to_asset = row.get("to")
    if _birdeye_asset_address(to_asset) == token_address:
        side, token_asset = "BUY", to_asset
    elif _birdeye_asset_address(from_asset) == token_address:
        side, token_asset = "SELL", from_asset
    else:
        return None

    token_amount = _birdeye_asset_number(
        token_asset, "uiAmount", "ui_amount", "uiChangeAmount", "ui_change_amount",
    )
    price_usd = _birdeye_asset_number(
        token_asset, "price", "nearestPrice", "nearest_price",
    )
    if price_usd is None:
        price_usd = _number(row.get("tokenPrice", row.get("token_price")))
    volume_usd = _number(row.get("volumeUSD", row.get("volume_usd")))

    if token_amount is None or price_usd is None:
        return None
    token_amount = abs(token_amount)
    # TW-DATA-01B_BIRDEYE_FROM_TO_VOLUME
    # Birdeye's live /defi/txs/pair shape does not always include volumeUSD.
    # The selected token leg still proves both amount and USD unit price, so
    # derive the same notional deterministically instead of discarding the row.
    if volume_usd is None:
        volume_usd = token_amount * price_usd
    if price_usd < 0 or volume_usd < 0:
        return None

    instruction = str(row.get("insIndex", row.get("ins_index", "")))
    inner_instruction = str(row.get("innerInsIndex", row.get("inner_ins_index", "")))
    identity = ":".join(
        part for part in (tx_hash, instruction, inner_instruction) if part != ""
    )
    observed = datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
    return {
        "id": identity,
        "tx_hash": tx_hash,
        "timestamp": observed.isoformat().replace("+00:00", "Z"),
        "trader": str(row.get("owner") or "").strip() or None,
        "side": side,
        "price_usd": price_usd,
        "token_amount": token_amount,
        "volume_usd": volume_usd,
    }


def _normalize_birdeye_exact_pool_trades(
    payload: Any, token_address: str, pair_address: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return []
    data = payload.get("data")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in items:
        if not isinstance(row, dict):
            continue
        normalized = _normalize_birdeye_exact_pool_trade(
            row, token_address, pair_address,
        )
        if normalized is None or str(normalized["id"]) in seen:
            continue
        seen.add(str(normalized["id"]))
        result.append(normalized)
    result.sort(
        key=lambda item: (str(item.get("timestamp") or ""), str(item.get("id") or "")),
        reverse=True,
    )
    return result


def _birdeye_exact_pool_trades_provider(
    token_address: str,
    pair_address: str,
    request_get: Callable[..., Any],
) -> list[dict[str, Any]]:
    api_key = _birdeye_api_key()
    if not api_key:
        return []
    response = request_get(
        BIRDEYE_TRADES_PAIR_URL,
        params={
            "address": pair_address,
            "offset": 0,
            "limit": 50,
            "tx_type": "swap",
            "sort_type": "desc",
        },
        headers={"X-API-KEY": api_key, "x-chain": "solana"},
        timeout=10,
    )
    response.raise_for_status()
    return _normalize_birdeye_exact_pool_trades(
        response.json(), token_address, pair_address,
    )


# TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI
def _normalize_market_activity(payload: Any, pair_address: str) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict): return {}
    attrs = data.get("attributes") if isinstance(data.get("attributes"), dict) else {}
    returned = str(attrs.get("address") or "")
    data_id = str(data.get("id") or "")
    if returned != pair_address and not data_id.endswith("_" + pair_address): return {}
    tx = attrs.get("transactions") if isinstance(attrs.get("transactions"), dict) else {}
    vols = attrs.get("volume_usd") if isinstance(attrs.get("volume_usd"), dict) else {}
    windows = {}
    for tf in MARKET_ACTIVITY_WINDOWS:
        row = tx.get(tf) if isinstance(tx.get(tf), dict) else {}
        buys=_number(row.get("buys")); sells=_number(row.get("sells"))
        buyers=_number(row.get("buyers")); sellers=_number(row.get("sellers")); volume=_number(vols.get(tf))
        if all(v is None for v in (buys,sells,buyers,sellers,volume)): continue
        b=max(0,int(buys)) if buys is not None else None; se=max(0,int(sells)) if sells is not None else None
        total=b+se if b is not None and se is not None else None
        pct=(b/total*100.0) if total else None
        windows[tf]={"buys":b,"sells":se,"buyers":max(0,int(buyers)) if buyers is not None else None,"sellers":max(0,int(sellers)) if sellers is not None else None,"total_transactions":total,"buy_percent":round(pct,2) if pct is not None else None,"volume_usd":volume}
    return {"pair_address":pair_address,"windows":windows,"source":"GeckoTerminal exact-pool aggregate"}


def _load_market_activity_provider(pair_address: str, request_get: Callable[..., Any]) -> dict[str, Any]:
    response=request_get(GECKO_POOL_URL.format(pair_address=pair_address),timeout=10)
    response.raise_for_status()
    return _normalize_market_activity(response.json(),pair_address)


def _load_solana_discovery_transactions_provider(
    token_address: str,
    *,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    # Verified recent trades for one qualified exact Solana pool.
    address = str(token_address or "").strip()
    if not address or len(address) > 80 or "/" in address:
        return None

    public_feed = feed if feed is not None else load_solana_discovery_feed()
    candidate = _transaction_candidate(address, public_feed)
    if candidate is None:
        return None

    pair_address = str(candidate.get("pair_address") or "").strip()
    response = request_get(
        GECKO_TRADES_URL.format(pair_address=pair_address),
        params={"token": "base"},
        timeout=10,
    )
    response.raise_for_status()

    # TRANSACTIONS_FEED_V16B_MARKET_ACTIVITY_UI
    try:
        market_activity = _load_market_activity_provider(pair_address, request_get)
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        market_activity = {}

    transactions = _normalize_exact_pool_trades(response.json(), address)
    source = "GeckoTerminal exact-pool trades"
    if not transactions:
        try:
            fallback = _birdeye_exact_pool_trades_provider(
                address, pair_address, request_get,
            )
        except (requests.RequestException, RuntimeError, TypeError, ValueError, OSError):
            fallback = []
        if fallback:
            transactions = fallback
            source = "Birdeye exact-pool trades fallback"

    return {
        "token_address": address,
        "pair_address": pair_address,
        "transactions": transactions,
        "market_activity": market_activity,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }



# TRANSACTIONS_FEED_V14_FRESHNESS_DIAGNOSTICS
def _parse_transaction_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _transaction_freshness(
    payload: dict[str, Any],
    *,
    served_at: datetime,
    cache_hit: bool,
    stale: bool,
) -> dict[str, Any]:
    fetched_at = _parse_transaction_timestamp(payload.get("as_of"))
    rows = payload.get("transactions")
    latest_trade_at = None
    if isinstance(rows, list) and rows:
        first = rows[0] if isinstance(rows[0], dict) else {}
        latest_trade_at = _parse_transaction_timestamp(first.get("timestamp"))

    def age_seconds(newer: datetime | None, older: datetime | None) -> float | None:
        if newer is None or older is None:
            return None
        return max(0.0, round((newer - older).total_seconds(), 3))

    # TRANSACTIONS_FEED_V141_FRESHNESS_SEMANTICS_FIX
    # "Last trade age" describes market inactivity, not provider latency.
    # "API age" describes how old the provider snapshot is when served.
    return {
        "served_at": served_at.isoformat(),
        "provider_fetched_at": fetched_at.isoformat() if fetched_at else None,
        "latest_trade_at": latest_trade_at.isoformat() if latest_trade_at else None,
        "last_trade_age_seconds": age_seconds(served_at, latest_trade_at),
        "api_age_seconds": age_seconds(served_at, fetched_at),
        "cache_hit": bool(cache_hit),
        "stale": bool(stale),
    }


def _with_transaction_freshness(
    payload: dict[str, Any],
    *,
    cache_hit: bool,
    stale: bool = False,
) -> dict[str, Any]:
    copied = _copy_transaction_payload(payload)
    copied["freshness"] = _transaction_freshness(
        copied,
        served_at=datetime.now(timezone.utc),
        cache_hit=cache_hit,
        stale=stale,
    )
    if stale:
        copied["stale"] = True
    return copied


def _copy_transaction_payload(payload: dict[str, Any]) -> dict[str, Any]:
    copied = dict(payload)
    rows = payload.get("transactions")
    copied["transactions"] = (
        [dict(row) for row in rows if isinstance(row, dict)]
        if isinstance(rows, list)
        else []
    )
    activity=payload.get("market_activity")
    if isinstance(activity,dict):
        ac=dict(activity); windows=activity.get("windows")
        ac["windows"]={str(k):dict(v) for k,v in windows.items() if isinstance(v,dict)} if isinstance(windows,dict) else {}
        copied["market_activity"]=ac
    else:
        copied["market_activity"]={}
    return copied


def load_solana_discovery_transactions(
    token_address: str,
    *,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    if request_get is not requests.get or feed is not None:
        return _load_solana_discovery_transactions_provider(
            token_address,
            feed=feed,
            request_get=request_get,
        )

    address = str(token_address or "").strip()
    now = monotonic()
    with _TRANSACTION_CACHE_LOCK:
        _prune_transaction_cache(now)
        cached = _TRANSACTION_CACHE.get(address)
        if cached is not None and (now - cached[0]) < _TRANSACTION_TTL_SECONDS:
            return _with_transaction_freshness(cached[1], cache_hit=True, stale=False)

    try:
        payload = _load_solana_discovery_transactions_provider(
            token_address,
            feed=feed,
            request_get=request_get,
        )
    except requests.RequestException:
        current = monotonic()
        with _TRANSACTION_CACHE_LOCK:
            _prune_transaction_cache(current)
            cached = _TRANSACTION_CACHE.get(address)
            if cached is not None and (current - cached[0]) <= TRANSACTION_STALE_SECONDS:
                return _with_transaction_freshness(cached[1], cache_hit=True, stale=True)
        raise

    if payload is None:
        return None

    stored = _copy_transaction_payload(payload)
    current = monotonic()
    with _TRANSACTION_CACHE_LOCK:
        _TRANSACTION_CACHE[address] = (current, stored)
        _prune_transaction_cache(current)
    return _with_transaction_freshness(stored, cache_hit=False, stale=False)


def load_solana_discovery_token(
    token_address: str,
    *,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
    request_post: Callable[..., Any] = requests.post,
) -> dict[str, Any] | None:
    """Return one qualified exact-token workspace; never expose raw candidates."""
    address = str(token_address or "").strip()
    if not address or len(address) > 80 or "/" in address:
        return None
    if feed is None:
        candidate = load_solana_discovery_record(address)
    else:
        candidates = feed.get("candidates") if isinstance(feed, dict) else None
        if not isinstance(candidates, list):
            return None
        candidate = next(
            (item for item in candidates if isinstance(item, dict) and item.get("token_address") == address),
            None,
        )
    if candidate is None:
        return None

    detail = dict(candidate)
    if request_post is requests.post and feed is not None:
        detail.update({
            "mint_authority_observation": "Unavailable",
            "freeze_authority_observation": "Unavailable",
            "metadata_observation": "Unavailable",
        })
    else:
        detail.update(_mint_authorities(address, request_post))
    detail["quote_status"] = "STORED"
    detail["quote_label"] = "Stored collector observation"
    detail["chart"] = []
    detail["candlestick_timeframes"] = {
        "1m": [], "5m": [], "15m": [], "30m": [], "1H": [], "4H": [],
    }
    for timeframe_key in TRADER_TIMEFRAME_MINUTES:
        detail[timeframe_key] = None
    try:
        pair = _live_pair(candidate, request_get)
        if pair is not None:
            liquidity = pair.get("liquidity") if isinstance(pair.get("liquidity"), dict) else {}
            volume = pair.get("volume") if isinstance(pair.get("volume"), dict) else {}
            change = pair.get("priceChange") if isinstance(pair.get("priceChange"), dict) else {}
            info = pair.get("info") if isinstance(pair.get("info"), dict) else {}
            websites = info.get("websites") if isinstance(info.get("websites"), list) else []
            socials = info.get("socials") if isinstance(info.get("socials"), list) else []

            image_url = str(info.get("imageUrl") or "")
            if not image_url.startswith("https://"):
                image_url = ""

            website_url = ""
            for item in websites:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "")
                if url.startswith("https://"):
                    website_url = url
                    break

            telegram_url = ""
            twitter_url = ""
            for item in socials:
                if not isinstance(item, dict):
                    continue
                social_type = str(item.get("type") or "").lower()
                url = str(item.get("url") or "")
                if not url.startswith("https://"):
                    continue
                if social_type == "telegram" and not telegram_url:
                    telegram_url = url
                if social_type in {"twitter", "x"} and not twitter_url:
                    twitter_url = url

            live_age_label, live_age_hours = _live_pair_age(
                pair.get("pairCreatedAt")
            )
            if live_age_hours is not None:
                detail["pair_age"] = live_age_label
                detail["pair_age_hours"] = live_age_hours

            detail.update({
                "price_usd": _number(pair.get("priceUsd")),
                "liquidity_usd": _number(liquidity.get("usd")),
                "volume_24h_usd": _number(volume.get("h24")),
                "change_24h": _number(change.get("h24")),
                "market_cap": _number(pair.get("marketCap") or pair.get("fdv")),
                "dex_id": pair.get("dexId") or detail.get("dex_id"),
                "source_url": pair.get("url") or detail.get("source_url"),
                "token_image_url": image_url,
                "website_url": website_url,
                "telegram_url": telegram_url,
                "twitter_url": twitter_url,
                "quote_status": "LIVE",
                "quote_label": "Live exact-pool observation",
                "quote_as_of": datetime.now(timezone.utc).isoformat(),
            })
    except (requests.RequestException, RuntimeError, ValueError, TypeError):
        pass
    four_hour_candles: list[dict[str, float]] = []
    minute_candles: list[dict[str, float]] = []
    hourly_candles: list[dict[str, float]] = []

    try:
        four_hour_candles = _chart(candidate, request_get)
        detail["chart"] = four_hour_candles
    except (requests.RequestException, RuntimeError, ValueError, TypeError):
        detail["chart"] = []

    try:
        minute_candles = _minute_candles(candidate, request_get)
        detail.update(_trader_timeframe_changes(minute_candles))
    except (requests.RequestException, RuntimeError, ValueError, TypeError):
        minute_candles = []

    try:
        hourly_candles = _hourly_candles(candidate, request_get)
    except (requests.RequestException, RuntimeError, ValueError, TypeError):
        hourly_candles = []

    detail["candlestick_timeframes"] = _candlestick_timeframes(
        minute_candles,
        hourly_candles,
        four_hour_candles,
    )
    detail["feed_updated_label"] = (
        str(feed.get("updated_label") or "Unknown")
        if isinstance(feed, dict)
        else str(candidate.get("feed_updated_label") or "Unknown")
    )
    return detail
