"""Read-only Jupiter Trending adapter for DexSato Solana Discovery."""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable

import requests

from application.dexscreener_sol_pair_resolver import (
    ExactSolPairResolverUnavailable,
    resolve_exact_sol_pairs,
)


JUPITER_TRENDING_1H_URL = "https://api.jup.ag/tokens/v2/toptrending/1h"
TRENDING_FETCH_LIMIT = 50
TRENDING_DISPLAY_LIMIT = 30
TRENDING_MIN_EXACT_POOL_LIQUIDITY_USD = 100_000.0
TRENDING_CACHE_SECONDS = 60.0
_CACHE_LOCK = threading.Lock()
_CACHE_AT = 0.0
_CACHE_PAYLOAD: dict[str, Any] | None = None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _volume_1h(stats: dict[str, Any]) -> float | None:
    buy = _number(stats.get("buyVolume"))
    sell = _number(stats.get("sellVolume"))
    if buy is None and sell is None:
        return None
    return max(0.0, buy or 0.0) + max(0.0, sell or 0.0)


def _normalize_trending_row(token: dict[str, Any], pair: dict[str, Any]) -> dict[str, Any]:
    stats = token.get("stats1h")
    if not isinstance(stats, dict):
        stats = {}
    mint = str(token.get("id") or "").strip()
    return {
        "token_address": mint,
        "symbol": str(token.get("symbol") or "Unknown").strip()[:40],
        "name": str(token.get("name") or "Unknown token").strip()[:100],
        "icon": str(token.get("icon") or "").strip(),
        "price_usd": _number(token.get("usdPrice")),
        "change_1h": _number(stats.get("priceChange")),
        "volume_1h_usd": _volume_1h(stats),
        # Exact-pool liquidity and pair identity come from the canonical
        # token/WSOL resolver, not from Jupiter aggregate token liquidity.
        "liquidity_usd": _number(pair.get("liquidity_usd")),
        "pair_address": str(pair.get("pair_address") or "").strip(),
        "dex_id": str(pair.get("dex_id") or "").strip(),
        "quote_address": str(pair.get("quote_address") or "").strip(),
        "quote_symbol": str(pair.get("quote_symbol") or "SOL").strip(),
        "trending_rank": token.get("_trending_rank"),
        # Never fabricate engine output. Existing read-only signal data can be
        # wired later without modifying engine behavior.
        "detected_signal": None,
        # TRENDING-02C will introduce a separate market-feed workspace route.
        # Keep rows non-clickable until that route/data contract is available.
        "href": f"/market/trending/{mint}",
    }


def _fetch_trending(
    *,
    request_get: Callable[..., Any],
    pair_resolver: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    api_key = os.getenv("JUPITER_API_KEY", "").strip()
    if not api_key:
        return {
            "connected": False,
            "status": "not_configured",
            "message": "Trending data is unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    try:
        response = request_get(
            JUPITER_TRENDING_1H_URL,
            params={"limit": TRENDING_FETCH_LIMIT},
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return {
            "connected": False,
            "status": "unavailable",
            "message": "Trending data is temporarily unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    if not isinstance(payload, list):
        return {
            "connected": False,
            "status": "invalid_response",
            "message": "Trending data is temporarily unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    ranked_tokens: list[dict[str, Any]] = []
    seen: set[str] = set()

    for rank, token in enumerate(payload[:TRENDING_FETCH_LIMIT], start=1):
        if not isinstance(token, dict):
            continue
        mint = str(token.get("id") or "").strip()
        if not mint or mint in seen:
            continue
        seen.add(mint)
        ranked = dict(token)
        ranked["_trending_rank"] = rank
        ranked_tokens.append(ranked)

    try:
        resolution = pair_resolver(
            [str(token.get("id") or "").strip() for token in ranked_tokens],
            min_liquidity_usd=TRENDING_MIN_EXACT_POOL_LIQUIDITY_USD,
            request_get=request_get,
        )
    except (ExactSolPairResolverUnavailable, RuntimeError, TypeError, ValueError):
        return {
            "connected": False,
            "status": "pair_resolution_unavailable",
            "message": "Trending exact SOL-pair resolution is temporarily unavailable.",
            "rows": [],
            "raw_count": min(len(payload), TRENDING_FETCH_LIMIT),
            "eligible_count": 0,
        }

    pair_rows = resolution.get("rows") if isinstance(resolution, dict) else None
    if not isinstance(pair_rows, list):
        pair_rows = []

    pair_by_mint = {
        str(pair.get("token_address") or "").strip(): pair
        for pair in pair_rows
        if isinstance(pair, dict) and str(pair.get("token_address") or "").strip()
    }

    rows: list[dict[str, Any]] = []
    for token in ranked_tokens:
        mint = str(token.get("id") or "").strip()
        pair = pair_by_mint.get(mint)
        if pair is None:
            continue
        rows.append(_normalize_trending_row(token, pair))
        if len(rows) >= TRENDING_DISPLAY_LIMIT:
            break

    return {
        "connected": True,
        "status": "live",
        "message": (
            "Jupiter toptrending / 1h ranked tokens resolved to canonical "
            "exact WSOL pools."
        ),
        "rows": rows,
        "raw_count": min(len(payload), TRENDING_FETCH_LIMIT),
        "eligible_count": len(rows),
        "provider_pair_count": (
            resolution.get("provider_pair_count")
            if isinstance(resolution, dict)
            else None
        ),
        "fetch_limit": TRENDING_FETCH_LIMIT,
        "display_limit": TRENDING_DISPLAY_LIMIT,
        "min_liquidity_usd": TRENDING_MIN_EXACT_POOL_LIQUIDITY_USD,
    }


def load_jupiter_trending_feed(
    *,
    request_get: Callable[..., Any] = requests.get,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Return cached Trending/1h data; failures never block Discovery rendering."""
    global _CACHE_AT, _CACHE_PAYLOAD

    now = now_monotonic()
    with _CACHE_LOCK:
        if (
            _CACHE_PAYLOAD is not None
            and now >= _CACHE_AT
            and (now - _CACHE_AT) < TRENDING_CACHE_SECONDS
        ):
            return dict(_CACHE_PAYLOAD)

    payload = _fetch_trending(
        request_get=request_get,
        pair_resolver=pair_resolver,
    )

    with _CACHE_LOCK:
        _CACHE_AT = now
        _CACHE_PAYLOAD = dict(payload)

    return payload
