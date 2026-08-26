"""Exact-token read model for the Solana Discovery D4 workspace."""

from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable

import requests

from application.solana_discovery_feed_service import load_solana_discovery_feed


DEXSCREENER_PAIR_URL = "https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"

# TRANSACTIONS_FEED_V10_EXACT_POOL_SERVICE
GECKO_TRADES_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/"
    "{pair_address}/trades"
)
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


def _live_pair(candidate: dict[str, Any], request_get: Callable[..., Any]) -> dict[str, Any] | None:
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


def _chart_provider(candidate: dict[str, Any], request_get: Callable[..., Any]) -> list[dict[str, float]]:
    pair_address = str(candidate.get("pair_address") or "")
    if not pair_address:
        return []
    response = request_get(
        GECKO_OHLCV_URL.format(pair_address=pair_address),
        params={"aggregate": 4, "limit": 90, "currency": "usd", "token": "base"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    attributes = data.get("attributes") if isinstance(data, dict) else None
    rows = attributes.get("ohlcv_list") if isinstance(attributes, dict) else None
    if not isinstance(rows, list):
        return []
    candles: list[dict[str, float]] = []
    for row in reversed(rows):
        if not isinstance(row, list) or len(row) < 6:
            continue
        values = [_number(value) for value in row[:6]]
        if any(value is None for value in values):
            continue
        candles.append({
            "time": values[0], "open": values[1], "high": values[2],
            "low": values[3], "close": values[4], "volume": values[5],
        })
    return candles



def _minute_candles_provider(
    candidate: dict[str, Any],
    request_get: Callable[..., Any],
) -> list[dict[str, float]]:
    pair_address = str(candidate.get("pair_address") or "")
    if not pair_address:
        return []
    response = request_get(
        GECKO_MINUTE_OHLCV_URL.format(pair_address=pair_address),
        params={
            "aggregate": 1,
            "limit": 300,
            "currency": "usd",
            "token": "base",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    attributes = data.get("attributes") if isinstance(data, dict) else None
    rows = attributes.get("ohlcv_list") if isinstance(attributes, dict) else None
    if not isinstance(rows, list):
        return []

    candles: list[dict[str, float]] = []
    for row in reversed(rows):
        if not isinstance(row, list) or len(row) < 6:
            continue
        values = [_number(value) for value in row[:6]]
        if any(value is None for value in values):
            continue
        candles.append({
            "time": values[0],
            "open": values[1],
            "high": values[2],
            "low": values[3],
            "close": values[4],
            "volume": values[5],
        })
    return candles


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
    if not pair_address:
        return []
    response = request_get(
        GECKO_HOURLY_OHLCV_URL.format(pair_address=pair_address),
        params={
            "aggregate": 1,
            "limit": 120,
            "currency": "usd",
            "token": "base",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    attributes = data.get("attributes") if isinstance(data, dict) else None
    rows = attributes.get("ohlcv_list") if isinstance(attributes, dict) else None
    if not isinstance(rows, list):
        return []

    candles: list[dict[str, float]] = []
    for row in reversed(rows):
        if not isinstance(row, list) or len(row) < 6:
            continue
        values = [_number(value) for value in row[:6]]
        if any(value is None for value in values):
            continue
        candles.append({
            "time": values[0],
            "open": values[1],
            "high": values[2],
            "low": values[3],
            "close": values[4],
            "volume": values[5],
        })
    return candles



# TRANSACTIONS_FEED_V123_PROVIDER_RESILIENCE
_OHLCV_CACHE: dict[tuple[str, str], tuple[float, list[dict[str, float]]]] = {}
_TRANSACTION_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}

_OHLCV_TTL_SECONDS = {
    "minute": 45.0,
    "hour": 60.0,
    "4h": 60.0,
}
_TRANSACTION_TTL_SECONDS = 20.0


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
    if not pair_address:
        return []

    key = (pair_address, cache_kind)
    now = monotonic()
    cached = _OHLCV_CACHE.get(key)
    ttl = _OHLCV_TTL_SECONDS[cache_kind]

    if cached is not None and (now - cached[0]) < ttl:
        return _copy_candles(cached[1])

    try:
        rows = provider(candidate, request_get)
    except requests.RequestException:
        if cached is not None:
            return _copy_candles(cached[1])
        raise

    _OHLCV_CACHE[key] = (now, _copy_candles(rows))
    return _copy_candles(rows)


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
    if timeframe not in LIVE_CANDLE_SECONDS or live_price is None or live_price <= 0:
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

    return {
        "token_address": address,
        "pair_address": pair_address,
        "transactions": _normalize_exact_pool_trades(response.json(), address),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "GeckoTerminal exact-pool trades",
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
    cached = _TRANSACTION_CACHE.get(address)

    if cached is not None and (now - cached[0]) < _TRANSACTION_TTL_SECONDS:
        return _with_transaction_freshness(
            cached[1],
            cache_hit=True,
            stale=False,
        )

    try:
        payload = _load_solana_discovery_transactions_provider(
            token_address,
            feed=feed,
            request_get=request_get,
        )
    except requests.RequestException:
        if cached is not None:
            return _with_transaction_freshness(
                cached[1],
                cache_hit=True,
                stale=True,
            )
        raise

    if payload is None:
        return None

    stored = _copy_transaction_payload(payload)
    _TRANSACTION_CACHE[address] = (now, stored)
    return _with_transaction_freshness(
        stored,
        cache_hit=False,
        stale=False,
    )


def load_solana_discovery_token(
    token_address: str,
    *,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    """Return one qualified exact-token workspace; never expose raw candidates."""
    address = str(token_address or "").strip()
    if not address or len(address) > 80 or "/" in address:
        return None
    public_feed = feed if feed is not None else load_solana_discovery_feed()
    candidates = public_feed.get("candidates") if isinstance(public_feed, dict) else None
    if not isinstance(candidates, list):
        return None
    candidate = next(
        (item for item in candidates if isinstance(item, dict) and item.get("token_address") == address),
        None,
    )
    if candidate is None:
        return None

    detail = dict(candidate)
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
    detail["feed_updated_label"] = public_feed.get("updated_label")
    return detail
