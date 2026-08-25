"""Exact-token read model for the Solana Discovery D4 workspace."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import requests

from application.solana_discovery_feed_service import load_solana_discovery_feed


DEXSCREENER_PAIR_URL = "https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
GECKO_OHLCV_URL = (
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


def _chart(candidate: dict[str, Any], request_get: Callable[..., Any]) -> list[dict[str, float]]:
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



def _minute_candles(
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
    try:
        detail["chart"] = _chart(candidate, request_get)
    except (requests.RequestException, RuntimeError, ValueError, TypeError):
        detail["chart"] = []
    try:
        minute_candles = _minute_candles(candidate, request_get)
        detail.update(_trader_timeframe_changes(minute_candles))
    except (requests.RequestException, RuntimeError, ValueError, TypeError):
        pass
    detail["feed_updated_label"] = public_feed.get("updated_label")
    return detail
