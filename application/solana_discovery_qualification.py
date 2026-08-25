"""Bounded exact-pool market enrichment for Solana Discovery candidates."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any, Callable

import requests


PAIR_URL = "https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
MIN_LIQUIDITY_USD = 5_000.0
MIN_VOLUME_24H_USD = 1_000.0
MAX_CANDIDATES_CHECKED = 12
MI_V40_ROTATING_ENRICHMENT = True
_ENRICHMENT_CURSOR = 0
_ENRICHMENT_CURSOR_LOCK = Lock()
MAX_PUBLIC_CANDIDATES = 8
CACHE_SECONDS = 75
REQUEST_TIMEOUT_SECONDS = 6
_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_CACHE_LOCK = Lock()


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _same(value: Any, expected: Any) -> bool:
    return str(value or "").strip() == str(expected or "").strip()


def _pair_age_label(created_at: Any, now: datetime) -> str:
    try:
        created = datetime.fromtimestamp(float(created_at) / 1000, tz=timezone.utc)
        hours = max(0, int((now - created).total_seconds() / 3600))
    except (TypeError, ValueError, OSError, OverflowError):
        return "Unavailable"
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def _cached_pair(
    pair_address: str,
    request_get: Callable[..., Any],
) -> dict[str, Any] | None:
    current = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(pair_address)
        if cached and current - cached[0] < CACHE_SECONDS:
            return cached[1]
    try:
        response = request_get(
            PAIR_URL.format(pair_address=pair_address),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
        result = next((item for item in pairs if isinstance(item, dict) and _same(item.get("pairAddress"), pair_address)), None)
    except (requests.RequestException, ValueError, TypeError, StopIteration):
        result = None
    with _CACHE_LOCK:
        _CACHE[pair_address] = (current, result)
    return result


def qualify_candidate(
    observed: dict[str, Any],
    pair: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any] | None:
    """Reject ambiguous identities, missing market evidence and weak activity."""
    if not isinstance(pair, dict):
        return None
    token_address = str(observed.get("token_address") or "").strip()
    pair_address = str(observed.get("pair_address") or "").strip()
    base = pair.get("baseToken") if isinstance(pair.get("baseToken"), dict) else {}
    quote = pair.get("quoteToken") if isinstance(pair.get("quoteToken"), dict) else {}
    if not token_address or not pair_address:
        return None
    if pair.get("chainId") != "solana" or not _same(pair.get("pairAddress"), pair_address):
        return None
    if not _same(base.get("address"), token_address):
        return None
    liquidity = _number((pair.get("liquidity") or {}).get("usd"))
    volume = _number((pair.get("volume") or {}).get("h24"))
    price = _number(pair.get("priceUsd"))
    if liquidity is None or volume is None or price is None:
        return None
    if liquidity < MIN_LIQUIDITY_USD or volume < MIN_VOLUME_24H_USD:
        return None
    return {
        "token_address": token_address,
        "pair_address": pair_address,
        "symbol": str(base.get("symbol") or observed.get("symbol") or "Unknown"),
        "name": str(base.get("name") or observed.get("name") or "Unknown token"),
        "quote_symbol": str(quote.get("symbol") or "Unknown"),
        "dex_id": str(pair.get("dexId") or "Unknown"),
        "price_usd": price,
        "liquidity_usd": liquidity,
        "volume_24h_usd": volume,
        "pair_age": _pair_age_label(pair.get("pairCreatedAt"), now),
        "evidence": "Verified Solana pool with observable liquidity and 24h activity.",
        "risk_label": "Token security not independently verified",
        "source": "DexScreener exact pair",
        "source_url": str(pair.get("url") or ""),
        "last_seen_at": str(observed.get("last_seen_at") or ""),
    }


def qualify_discovery_candidates(
    candidates: dict[str, Any],
    *,
    now: datetime,
    request_get: Callable[..., Any] = requests.get,
) -> list[dict[str, Any]]:
    """Enrich only a bounded, newest-first set of unique resolved pools."""
    resolved = [item for item in candidates.values() if isinstance(item, dict) and item.get("token_address") and item.get("pair_address")]
    resolved.sort(key=lambda item: str(item.get("last_seen_at") or ""), reverse=True)

    # MI v4.0: deduplicate the whole resolved universe first, then rotate the
    # bounded enrichment window.  This preserves the existing API budget while
    # preventing older pools from being permanently starved by newer arrivals.
    unique_resolved: list[dict[str, Any]] = []
    seen_tokens: set[str] = set()
    seen_pairs: set[str] = set()
    for item in resolved:
        token = str(item["token_address"])
        pool = str(item["pair_address"])
        if token in seen_tokens or pool in seen_pairs:
            continue
        seen_tokens.add(token)
        seen_pairs.add(pool)
        unique_resolved.append(item)

    selected: list[dict[str, Any]] = []
    if unique_resolved:
        global _ENRICHMENT_CURSOR
        with _ENRICHMENT_CURSOR_LOCK:
            start = _ENRICHMENT_CURSOR % len(unique_resolved)
            take = min(MAX_CANDIDATES_CHECKED, len(unique_resolved))
            selected = [
                unique_resolved[(start + offset) % len(unique_resolved)]
                for offset in range(take)
            ]
            _ENRICHMENT_CURSOR = (start + take) % len(unique_resolved)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(selected)))) as executor:
        futures = {executor.submit(_cached_pair, str(item["pair_address"]), request_get): item for item in selected}
        for future in as_completed(futures):
            try:
                qualified = qualify_candidate(futures[future], future.result(), now=now)
            except Exception:
                continue
            if qualified is not None:
                results.append(qualified)
    results.sort(key=lambda item: (item["last_seen_at"], item["volume_24h_usd"]), reverse=True)
    return results[:MAX_PUBLIC_CANDIDATES]
