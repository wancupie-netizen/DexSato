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
from application.trending_signal_interpreter import interpret_trending_signal


JUPITER_TRENDING_1H_URL = "https://api.jup.ag/tokens/v2/toptrending/1h"
TRENDING_FETCH_LIMIT = 50
TRENDING_DISPLAY_LIMIT = 30
TRENDING_MIN_EXACT_POOL_LIQUIDITY_USD = 100_000.0
TRENDING_CACHE_SECONDS = 60.0
# Workspace continuity only: a token that was genuinely eligible and rendered
# may remain open briefly even if Jupiter's live Top Trending ranking refreshes.
# This does not put the token back into the public Trending list.
TRENDING_WORKSPACE_GRACE_SECONDS = 900.0
_CACHE_LOCK = threading.Lock()
_CACHE_AT = 0.0
_CACHE_PAYLOAD: dict[str, Any] | None = None
_RECENT_ELIGIBLE_ROWS: dict[str, tuple[float, dict[str, Any]]] = {}

# TOP-TRADED-03A: independent Jupiter Top Traded / 24h market feed.
# Ranking comes only from Jupiter. Eligibility remains exact token/WSOL pool
# resolution with the same $100k minimum used by the market-feed policy.
JUPITER_TOP_TRADED_24H_URL = "https://api.jup.ag/tokens/v2/toptraded/24h"
TOP_TRADED_FETCH_LIMIT = 50
TOP_TRADED_DISPLAY_LIMIT = 30
TOP_TRADED_MIN_EXACT_POOL_LIQUIDITY_USD = 100_000.0
TOP_TRADED_CACHE_SECONDS = 60.0
_TOP_TRADED_CACHE_LOCK = threading.Lock()
_TOP_TRADED_CACHE_AT = 0.0
_TOP_TRADED_CACHE_PAYLOAD: dict[str, Any] | None = None
TOP_TRADED_WORKSPACE_GRACE_SECONDS = 900.0
_TOP_TRADED_RECENT_ELIGIBLE_ROWS: dict[str, tuple[float, dict[str, Any]]] = {}

# ORGANIC-FLOW-04A: Jupiter Organic Score / 1h market feed.
# Jupiter ordering is preserved. DexSato only applies exact token/WSOL
# eligibility plus the shared $100k exact-pool liquidity floor.
JUPITER_ORGANIC_FLOW_1H_URL = "https://api.jup.ag/tokens/v2/toporganicscore/1h"
ORGANIC_FLOW_FETCH_LIMIT = 50
ORGANIC_FLOW_DISPLAY_LIMIT = 30
ORGANIC_FLOW_MIN_EXACT_POOL_LIQUIDITY_USD = 100_000.0
ORGANIC_FLOW_CACHE_SECONDS = 60.0
_ORGANIC_FLOW_CACHE_LOCK = threading.Lock()
_ORGANIC_FLOW_CACHE_AT = 0.0
_ORGANIC_FLOW_CACHE_PAYLOAD: dict[str, Any] | None = None
ORGANIC_FLOW_WORKSPACE_GRACE_SECONDS = 900.0
_ORGANIC_FLOW_RECENT_ELIGIBLE_ROWS: dict[
    str, tuple[float, dict[str, Any]]
] = {}


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
        # Stateless market intelligence: canonical DexSato price/volume/
        # liquidity semantics plus transparent Jupiter 1h evidence.
        "detected_signal": interpret_trending_signal(stats),
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


def _normalize_top_traded_row(
    token: dict[str, Any],
    pair: dict[str, Any],
) -> dict[str, Any]:
    """Normalize one Jupiter-ranked token without changing ranking semantics."""
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
        # Top Traded ranking is 24h. The table metric remains 1h so all
        # market tabs stay directly comparable.
        "change_1h": _number(stats.get("priceChange")),
        "volume_1h_usd": _volume_1h(stats),
        "liquidity_usd": _number(pair.get("liquidity_usd")),
        "pair_address": str(pair.get("pair_address") or "").strip(),
        "dex_id": str(pair.get("dex_id") or "").strip(),
        "quote_address": str(pair.get("quote_address") or "").strip(),
        "quote_symbol": str(pair.get("quote_symbol") or "SOL").strip(),
        "top_traded_rank": token.get("_top_traded_rank"),
        "detected_signal": interpret_trending_signal(stats),
        "market_source": "jupiter_toptraded_24h",
        "href": f"/market/top-traded/{mint}",
    }


def _fetch_top_traded(
    *,
    request_get: Callable[..., Any],
    pair_resolver: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    api_key = os.getenv("JUPITER_API_KEY", "").strip()
    if not api_key:
        return {
            "connected": False,
            "status": "not_configured",
            "message": "Top Traded data is unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    try:
        response = request_get(
            JUPITER_TOP_TRADED_24H_URL,
            params={"limit": TOP_TRADED_FETCH_LIMIT},
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return {
            "connected": False,
            "status": "unavailable",
            "message": "Top Traded data is temporarily unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    if not isinstance(payload, list):
        return {
            "connected": False,
            "status": "invalid_response",
            "message": "Top Traded data is temporarily unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    ranked_tokens: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, token in enumerate(payload[:TOP_TRADED_FETCH_LIMIT], start=1):
        if not isinstance(token, dict):
            continue
        mint = str(token.get("id") or "").strip()
        if not mint or mint in seen:
            continue
        seen.add(mint)
        ranked = dict(token)
        ranked["_top_traded_rank"] = rank
        ranked_tokens.append(ranked)

    try:
        resolution = pair_resolver(
            [str(token.get("id") or "").strip() for token in ranked_tokens],
            min_liquidity_usd=TOP_TRADED_MIN_EXACT_POOL_LIQUIDITY_USD,
            request_get=request_get,
        )
    except (ExactSolPairResolverUnavailable, RuntimeError, TypeError, ValueError):
        return {
            "connected": False,
            "status": "pair_resolution_unavailable",
            "message": (
                "Top Traded exact SOL-pair resolution is temporarily unavailable."
            ),
            "rows": [],
            "raw_count": min(len(payload), TOP_TRADED_FETCH_LIMIT),
            "eligible_count": 0,
        }

    pair_rows = resolution.get("rows") if isinstance(resolution, dict) else None
    if not isinstance(pair_rows, list):
        pair_rows = []

    pair_by_mint = {
        str(pair.get("token_address") or "").strip(): pair
        for pair in pair_rows
        if isinstance(pair, dict)
        and str(pair.get("token_address") or "").strip()
    }

    rows: list[dict[str, Any]] = []
    for token in ranked_tokens:
        mint = str(token.get("id") or "").strip()
        pair = pair_by_mint.get(mint)
        if pair is None:
            continue
        rows.append(_normalize_top_traded_row(token, pair))
        if len(rows) >= TOP_TRADED_DISPLAY_LIMIT:
            break

    return {
        "connected": True,
        "status": "live",
        "message": (
            "Jupiter toptraded / 24h ranked tokens resolved to canonical "
            "exact WSOL pools."
        ),
        "rows": rows,
        "raw_count": min(len(payload), TOP_TRADED_FETCH_LIMIT),
        "eligible_count": len(rows),
        "provider_pair_count": (
            resolution.get("provider_pair_count")
            if isinstance(resolution, dict)
            else None
        ),
        "fetch_limit": TOP_TRADED_FETCH_LIMIT,
        "display_limit": TOP_TRADED_DISPLAY_LIMIT,
        "min_liquidity_usd": TOP_TRADED_MIN_EXACT_POOL_LIQUIDITY_USD,
        "ranking_window": "24h",
        "display_metric_window": "1h",
    }


def _normalize_organic_flow_row(
    token: dict[str, Any],
    pair: dict[str, Any],
) -> dict[str, Any]:
    """Normalize one Jupiter Organic Score row without changing its rank."""
    stats = token.get("stats1h")
    if not isinstance(stats, dict):
        stats = {}

    mint = str(token.get("id") or "").strip()
    organic_score = _number(token.get("organicScore"))

    return {
        "token_address": mint,
        "symbol": str(token.get("symbol") or "Unknown").strip()[:40],
        "name": str(token.get("name") or "Unknown token").strip()[:100],
        "icon": str(token.get("icon") or "").strip(),
        "price_usd": _number(token.get("usdPrice")),
        "change_1h": _number(stats.get("priceChange")),
        "volume_1h_usd": _volume_1h(stats),
        "liquidity_usd": _number(pair.get("liquidity_usd")),
        "pair_address": str(pair.get("pair_address") or "").strip(),
        "dex_id": str(pair.get("dex_id") or "").strip(),
        "quote_address": str(pair.get("quote_address") or "").strip(),
        "quote_symbol": str(pair.get("quote_symbol") or "SOL").strip(),
        "organic_flow_rank": token.get("_organic_flow_rank"),
        # Preserve provider evidence if Jupiter supplies it. DexSato does not
        # compute, reinterpret or use this score for eligibility/reranking.
        "organic_score": organic_score,
        "detected_signal": interpret_trending_signal(stats),
        "market_source": "jupiter_toporganicscore_1h",
        "ranking_window": "1h",
        "display_metric_window": "1h",
        "href": f"/market/organic-flow/{mint}",
    }


def _fetch_organic_flow(
    *,
    request_get: Callable[..., Any],
    pair_resolver: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    api_key = os.getenv("JUPITER_API_KEY", "").strip()
    if not api_key:
        return {
            "connected": False,
            "status": "not_configured",
            "message": "Organic Flow data is unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    try:
        response = request_get(
            JUPITER_ORGANIC_FLOW_1H_URL,
            params={"limit": ORGANIC_FLOW_FETCH_LIMIT},
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return {
            "connected": False,
            "status": "unavailable",
            "message": "Organic Flow data is temporarily unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    if not isinstance(payload, list):
        return {
            "connected": False,
            "status": "invalid_response",
            "message": "Organic Flow data is temporarily unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    ranked_tokens: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rank, token in enumerate(payload[:ORGANIC_FLOW_FETCH_LIMIT], start=1):
        if not isinstance(token, dict):
            continue
        mint = str(token.get("id") or "").strip()
        if not mint or mint in seen:
            continue
        seen.add(mint)
        ranked = dict(token)
        ranked["_organic_flow_rank"] = rank
        ranked_tokens.append(ranked)

    try:
        resolution = pair_resolver(
            [str(token.get("id") or "").strip() for token in ranked_tokens],
            min_liquidity_usd=ORGANIC_FLOW_MIN_EXACT_POOL_LIQUIDITY_USD,
            request_get=request_get,
        )
    except (ExactSolPairResolverUnavailable, RuntimeError, TypeError, ValueError):
        return {
            "connected": False,
            "status": "pair_resolution_unavailable",
            "message": (
                "Organic Flow exact SOL-pair resolution is temporarily unavailable."
            ),
            "rows": [],
            "raw_count": min(len(payload), ORGANIC_FLOW_FETCH_LIMIT),
            "eligible_count": 0,
        }

    pair_rows = resolution.get("rows") if isinstance(resolution, dict) else None
    if not isinstance(pair_rows, list):
        pair_rows = []

    pair_by_mint = {
        str(pair.get("token_address") or "").strip(): pair
        for pair in pair_rows
        if isinstance(pair, dict)
        and str(pair.get("token_address") or "").strip()
    }

    rows: list[dict[str, Any]] = []
    for token in ranked_tokens:
        mint = str(token.get("id") or "").strip()
        pair = pair_by_mint.get(mint)
        if pair is None:
            continue
        rows.append(_normalize_organic_flow_row(token, pair))
        if len(rows) >= ORGANIC_FLOW_DISPLAY_LIMIT:
            break

    return {
        "connected": True,
        "status": "live",
        "message": (
            "Jupiter toporganicscore / 1h ranked tokens resolved to canonical "
            "exact WSOL pools."
        ),
        "rows": rows,
        "raw_count": min(len(payload), ORGANIC_FLOW_FETCH_LIMIT),
        "eligible_count": len(rows),
        "provider_pair_count": (
            resolution.get("provider_pair_count")
            if isinstance(resolution, dict)
            else None
        ),
        "fetch_limit": ORGANIC_FLOW_FETCH_LIMIT,
        "display_limit": ORGANIC_FLOW_DISPLAY_LIMIT,
        "min_liquidity_usd": ORGANIC_FLOW_MIN_EXACT_POOL_LIQUIDITY_USD,
        "ranking_window": "1h",
        "display_metric_window": "1h",
    }


def _remember_organic_flow_eligible_rows(
    payload: dict[str, Any],
    *,
    observed_at: float,
) -> None:
    """Remember only rows already accepted by the live Organic Flow feed."""
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return

    for row in rows:
        if not isinstance(row, dict):
            continue
        mint = str(row.get("token_address") or "").strip()
        if mint:
            _ORGANIC_FLOW_RECENT_ELIGIBLE_ROWS[mint] = (
                observed_at,
                dict(row),
            )

    expired = [
        mint
        for mint, (seen_at, _row) in _ORGANIC_FLOW_RECENT_ELIGIBLE_ROWS.items()
        if observed_at < seen_at
        or (observed_at - seen_at) >= ORGANIC_FLOW_WORKSPACE_GRACE_SECONDS
    ]
    for mint in expired:
        _ORGANIC_FLOW_RECENT_ELIGIBLE_ROWS.pop(mint, None)


def load_recent_jupiter_organic_flow_row(
    token_address: str,
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any] | None:
    """Return a recently displayed eligible Organic Flow row."""
    address = str(token_address or "").strip()
    if not address:
        return None

    now = now_monotonic()
    with _ORGANIC_FLOW_CACHE_LOCK:
        item = _ORGANIC_FLOW_RECENT_ELIGIBLE_ROWS.get(address)
        if item is None:
            return None

        seen_at, row = item
        if (
            now < seen_at
            or (now - seen_at) >= ORGANIC_FLOW_WORKSPACE_GRACE_SECONDS
        ):
            _ORGANIC_FLOW_RECENT_ELIGIBLE_ROWS.pop(address, None)
            return None

        result = dict(row)
        result["organic_flow_feed_state"] = "recent"
        result["organic_flow_observed_age_seconds"] = max(
            0.0,
            now - seen_at,
        )
        return result


def load_jupiter_organic_flow_feed(
    *,
    request_get: Callable[..., Any] = requests.get,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Return cached Organic Flow / 1h data without touching Discovery state."""
    global _ORGANIC_FLOW_CACHE_AT, _ORGANIC_FLOW_CACHE_PAYLOAD

    now = now_monotonic()
    with _ORGANIC_FLOW_CACHE_LOCK:
        if (
            _ORGANIC_FLOW_CACHE_PAYLOAD is not None
            and now >= _ORGANIC_FLOW_CACHE_AT
            and (now - _ORGANIC_FLOW_CACHE_AT) < ORGANIC_FLOW_CACHE_SECONDS
        ):
            return dict(_ORGANIC_FLOW_CACHE_PAYLOAD)

    payload = _fetch_organic_flow(
        request_get=request_get,
        pair_resolver=pair_resolver,
    )

    with _ORGANIC_FLOW_CACHE_LOCK:
        _ORGANIC_FLOW_CACHE_AT = now
        _ORGANIC_FLOW_CACHE_PAYLOAD = dict(payload)
        if payload.get("connected") is True:
            _remember_organic_flow_eligible_rows(payload, observed_at=now)

    return payload


def _remember_top_traded_eligible_rows(
    payload: dict[str, Any],
    *,
    observed_at: float,
) -> None:
    """Remember only rows already accepted by the live Top Traded feed."""
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return

    for row in rows:
        if not isinstance(row, dict):
            continue
        mint = str(row.get("token_address") or "").strip()
        if mint:
            _TOP_TRADED_RECENT_ELIGIBLE_ROWS[mint] = (
                observed_at,
                dict(row),
            )

    expired = [
        mint
        for mint, (seen_at, _row) in _TOP_TRADED_RECENT_ELIGIBLE_ROWS.items()
        if observed_at < seen_at
        or (observed_at - seen_at) >= TOP_TRADED_WORKSPACE_GRACE_SECONDS
    ]
    for mint in expired:
        _TOP_TRADED_RECENT_ELIGIBLE_ROWS.pop(mint, None)


def load_recent_jupiter_top_traded_row(
    token_address: str,
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any] | None:
    """Return a recently displayed eligible Top Traded row."""
    address = str(token_address or "").strip()
    if not address:
        return None

    now = now_monotonic()
    with _TOP_TRADED_CACHE_LOCK:
        item = _TOP_TRADED_RECENT_ELIGIBLE_ROWS.get(address)
        if item is None:
            return None

        seen_at, row = item
        if (
            now < seen_at
            or (now - seen_at) >= TOP_TRADED_WORKSPACE_GRACE_SECONDS
        ):
            _TOP_TRADED_RECENT_ELIGIBLE_ROWS.pop(address, None)
            return None

        result = dict(row)
        result["top_traded_feed_state"] = "recent"
        result["top_traded_observed_age_seconds"] = max(
            0.0,
            now - seen_at,
        )
        return result


def load_jupiter_top_traded_feed(
    *,
    request_get: Callable[..., Any] = requests.get,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Return cached Top Traded / 24h data without touching Discovery state."""
    global _TOP_TRADED_CACHE_AT, _TOP_TRADED_CACHE_PAYLOAD

    now = now_monotonic()
    with _TOP_TRADED_CACHE_LOCK:
        if (
            _TOP_TRADED_CACHE_PAYLOAD is not None
            and now >= _TOP_TRADED_CACHE_AT
            and (now - _TOP_TRADED_CACHE_AT) < TOP_TRADED_CACHE_SECONDS
        ):
            return dict(_TOP_TRADED_CACHE_PAYLOAD)

    payload = _fetch_top_traded(
        request_get=request_get,
        pair_resolver=pair_resolver,
    )

    with _TOP_TRADED_CACHE_LOCK:
        _TOP_TRADED_CACHE_AT = now
        _TOP_TRADED_CACHE_PAYLOAD = dict(payload)
        if payload.get("connected") is True:
            _remember_top_traded_eligible_rows(payload, observed_at=now)

    return payload


def _remember_eligible_rows(
    payload: dict[str, Any],
    *,
    observed_at: float,
) -> None:
    """Remember only rows that already passed the live Trending eligibility flow."""
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return

    for row in rows:
        if not isinstance(row, dict):
            continue
        mint = str(row.get("token_address") or "").strip()
        if mint:
            _RECENT_ELIGIBLE_ROWS[mint] = (observed_at, dict(row))

    expired = [
        mint
        for mint, (seen_at, _row) in _RECENT_ELIGIBLE_ROWS.items()
        if observed_at < seen_at
        or (observed_at - seen_at) >= TRENDING_WORKSPACE_GRACE_SECONDS
    ]
    for mint in expired:
        _RECENT_ELIGIBLE_ROWS.pop(mint, None)


def load_recent_jupiter_trending_row(
    token_address: str,
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any] | None:
    """Return a recently displayed eligible row within the continuity window."""
    address = str(token_address or "").strip()
    if not address:
        return None

    now = now_monotonic()
    with _CACHE_LOCK:
        item = _RECENT_ELIGIBLE_ROWS.get(address)
        if item is None:
            return None

        seen_at, row = item
        if (
            now < seen_at
            or (now - seen_at) >= TRENDING_WORKSPACE_GRACE_SECONDS
        ):
            _RECENT_ELIGIBLE_ROWS.pop(address, None)
            return None

        result = dict(row)
        result["trending_feed_state"] = "recent"
        result["trending_observed_age_seconds"] = max(0.0, now - seen_at)
        return result


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
        if payload.get("connected") is True:
            _remember_eligible_rows(payload, observed_at=now)

    return payload
