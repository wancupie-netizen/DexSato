"""Read-only Jupiter Trending adapter for DexSato Solana Discovery."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

import requests

from application.dexscreener_sol_pair_resolver import (
    ExactSolPairResolverUnavailable,
    resolve_exact_sol_pair_groups,
    resolve_exact_sol_pairs,
)
from application.trending_signal_interpreter import interpret_trending_signal
from application.ranked_market_feed_store import RankedMarketFeedStore
from application.recent_market_store import (
    RECENT_V2_RETENTION_SECONDS,
    RecentMarketStore,
    RecentMarketStoreUnavailable,
)


JUPITER_TRENDING_1H_URL = "https://api.jup.ag/tokens/v2/toptrending/1h"
TRENDING_FETCH_LIMIT = 50
TRENDING_DISPLAY_LIMIT = 30
TRENDING_MIN_EXACT_POOL_LIQUIDITY_USD = 100_000.0
TRENDING_CACHE_SECONDS = 60.0
TRENDING_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS = 5 * 60.0
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
TOP_TRADED_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS = 10 * 60.0
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
ORGANIC_FLOW_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS = 5 * 60.0
_ORGANIC_FLOW_CACHE_LOCK = threading.Lock()
_ORGANIC_FLOW_CACHE_AT = 0.0
_ORGANIC_FLOW_CACHE_PAYLOAD: dict[str, Any] | None = None
ORGANIC_FLOW_WORKSPACE_GRACE_SECONDS = 900.0
_ORGANIC_FLOW_RECENT_ELIGIBLE_ROWS: dict[
    str, tuple[float, dict[str, Any]]
] = {}


# RECENT-05A: Jupiter Recent market feed.
# Recent means first pool creation time from Jupiter, not mint creation time.
# Provider order is preserved; DexSato only adds exact token/WSOL eligibility,
# the shared $100k exact-pool liquidity floor, and stateless signal context.
JUPITER_RECENT_URL = "https://api.jup.ag/tokens/v2/recent"
RECENT_FETCH_LIMIT = 50
RECENT_DISPLAY_LIMIT = 30
RECENT_MIN_EXACT_POOL_LIQUIDITY_USD = 25_000.0
RECENT_CACHE_SECONDS = 60.0
_RECENT_MARKET_CACHE_LOCK = threading.Lock()
_RECENT_MARKET_CACHE_AT = 0.0
_RECENT_MARKET_CACHE_PAYLOAD: dict[str, Any] | None = None
RECENT_WORKSPACE_GRACE_SECONDS = 900.0
_RECENT_RECENT_ELIGIBLE_ROWS: dict[
    str, tuple[float, dict[str, Any]]
] = {}
_RECENT_V2_STORE_INIT_LOCK = threading.Lock()
_RECENT_V2_STORE: RecentMarketStore | None = None
_RECENT_STORE_BOOTSTRAP_ATTEMPTED = False

_RANKED_MARKET_FEED_STORE = RankedMarketFeedStore()
_RANKED_MARKET_BOOTSTRAP_LOCK = threading.Lock()
_RANKED_MARKET_BOOTSTRAP_ATTEMPTED: set[str] = set()

_RANKED_REFRESH_LOCK = threading.Lock()
_RANKED_REFRESH_IN_FLIGHT = False
_RANKED_REFRESH_NEXT_ALLOWED_AT = 0.0
_RANKED_REFRESH_FAILURE_COOLDOWN_SECONDS = 60.0

_RANKED_LAST_GOOD_LOCK = threading.Lock()
_RANKED_REFRESH_OUTCOMES_LOCK = threading.Lock()
_RANKED_LAST_GOOD_AT: dict[str, float] = {}


def _ranked_last_good_age(
    name: str,
    *,
    now_monotonic: float,
) -> float | None:
    """Return monotonic age of one known successful ranked snapshot."""
    with _RANKED_LAST_GOOD_LOCK:
        observed_at = _RANKED_LAST_GOOD_AT.get(name)
    if observed_at is None:
        return None
    if now_monotonic < observed_at:
        return None
    return now_monotonic - observed_at


def _ranked_stale_is_servable(
    name: str,
    *,
    now_monotonic: float,
    max_age_seconds: float,
) -> bool:
    """Return whether one known last-good snapshot remains inside its hard age limit."""
    age = _ranked_last_good_age(
        name,
        now_monotonic=now_monotonic,
    )
    return age is not None and age <= max_age_seconds


def _remember_ranked_last_good(
    name: str,
    *,
    now_monotonic: float,
    existing_age_seconds: float = 0.0,
) -> None:
    """Remember the original observation time without resetting persistent LKG age."""
    age = max(0.0, float(existing_age_seconds))
    with _RANKED_LAST_GOOD_LOCK:
        _RANKED_LAST_GOOD_AT[name] = now_monotonic - age


def _try_begin_ranked_refresh(
    *,
    now_monotonic: float,
) -> bool:
    """Acquire process-local ownership for one ranked-group refresh."""
    global _RANKED_REFRESH_IN_FLIGHT

    with _RANKED_REFRESH_LOCK:
        if _RANKED_REFRESH_IN_FLIGHT:
            return False
        if now_monotonic < _RANKED_REFRESH_NEXT_ALLOWED_AT:
            return False
        _RANKED_REFRESH_IN_FLIGHT = True
        return True


def _finish_ranked_refresh(
    *,
    now_monotonic: float,
    failed: bool,
) -> None:
    """Release ranked refresh ownership and apply failure cooldown."""
    global _RANKED_REFRESH_IN_FLIGHT, _RANKED_REFRESH_NEXT_ALLOWED_AT

    with _RANKED_REFRESH_LOCK:
        if failed:
            _RANKED_REFRESH_NEXT_ALLOWED_AT = (
                now_monotonic + _RANKED_REFRESH_FAILURE_COOLDOWN_SECONDS
            )
        else:
            _RANKED_REFRESH_NEXT_ALLOWED_AT = 0.0
        _RANKED_REFRESH_IN_FLIGHT = False


def _load_ranked_market_bootstrap_once(
    key: str,
    *,
    max_age_seconds: float,
) -> dict[str, Any] | None:
    """Load one valid final feed payload from disk at most once per process."""
    with _RANKED_MARKET_BOOTSTRAP_LOCK:
        if key in _RANKED_MARKET_BOOTSTRAP_ATTEMPTED:
            return None
        _RANKED_MARKET_BOOTSTRAP_ATTEMPTED.add(key)

    loaded = _RANKED_MARKET_FEED_STORE.load(key, max_age_seconds=max_age_seconds)
    if loaded is None:
        return None
    payload, age_seconds = loaded
    if (
        payload.get("connected") is not True
        or payload.get("status") != "live"
        or not isinstance(payload.get("rows"), list)
    ):
        return None
    result = dict(payload)
    result["bootstrap_source"] = "persistent_lkg"
    result["bootstrap_age_seconds"] = max(0.0, float(age_seconds))
    return result


def _save_ranked_market_lkg(key: str, payload: dict[str, Any]) -> None:
    """Persist only successful final ranked-feed payloads."""
    if (
        payload.get("connected") is True
        and payload.get("status") == "live"
        and isinstance(payload.get("rows"), list)
    ):
        clean = dict(payload)
        clean.pop("bootstrap_source", None)
        clean.pop("bootstrap_age_seconds", None)
        _RANKED_MARKET_FEED_STORE.save(key, clean)


def _recent_v2_store() -> RecentMarketStore:
    """Return the process-local Recent V2 persistent-store instance."""
    global _RECENT_V2_STORE
    with _RECENT_V2_STORE_INIT_LOCK:
        if _RECENT_V2_STORE is None:
            _RECENT_V2_STORE = RecentMarketStore()
        return _RECENT_V2_STORE


def _load_recent_store_bootstrap_once() -> dict[str, Any] | None:
    """Restore the rolling Recent feed from its existing store once per process."""
    global _RECENT_STORE_BOOTSTRAP_ATTEMPTED

    if not os.getenv("JUPITER_API_KEY", "").strip():
        return None

    with _RECENT_MARKET_CACHE_LOCK:
        if _RECENT_STORE_BOOTSTRAP_ATTEMPTED:
            return None
        _RECENT_STORE_BOOTSTRAP_ATTEMPTED = True

    try:
        store = _recent_v2_store()
        store.expire()
        rows = store.active_rows()
    except RecentMarketStoreUnavailable:
        return None

    if not rows:
        return None

    return {
        "connected": True,
        "status": "live",
        "message": (
            "DexSato rolling 24h Recent feed restored from persisted "
            "eligible Jupiter Recent observations."
        ),
        "rows": rows,
        "eligible_count": len(rows),
        "retention_seconds": RECENT_V2_RETENTION_SECONDS,
        "market_feed": "recent_rolling_24h",
        "store_status": "ready",
        "ordering": "recent_first_pool_created_at_desc",
        "display_limit": RECENT_DISPLAY_LIMIT,
        "min_liquidity_usd": RECENT_MIN_EXACT_POOL_LIQUIDITY_USD,
        "bootstrap_source": "recent_market_store",
        "bootstrap_row_count": len(rows),
        "bootstrap_snapshot_refresh": False,
    }


def _merge_recent_snapshot_into_store(
    payload: dict[str, Any],
    *,
    store: RecentMarketStore | None = None,
) -> dict[str, Any]:
    """Persist eligible snapshot rows and expose the rolling 24h Recent feed."""
    if payload.get("connected") is not True:
        return dict(payload)

    rows = payload.get("rows")
    snapshot_rows = [
        dict(row)
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict)
    ]
    snapshot_eligible_count = len(snapshot_rows)

    try:
        active_store = store or _recent_v2_store()
        for row in snapshot_rows:
            active_store.upsert(row)
        active_store.expire()
        rolling_rows = active_store.active_rows()
    except RecentMarketStoreUnavailable:
        fallback = dict(payload)
        fallback["rows"] = snapshot_rows
        fallback["snapshot_eligible_count"] = snapshot_eligible_count
        fallback["eligible_count"] = snapshot_eligible_count
        fallback["retention_seconds"] = RECENT_V2_RETENTION_SECONDS
        fallback["market_feed"] = "recent_live_snapshot"
        fallback["store_status"] = "unavailable"
        fallback["message"] = (
            "Jupiter Recent live snapshot is available. Rolling 24h "
            "persistence is temporarily unavailable."
        )
        return fallback

    merged = dict(payload)
    merged["rows"] = rolling_rows
    merged["snapshot_eligible_count"] = snapshot_eligible_count
    merged["eligible_count"] = len(rolling_rows)
    merged["retention_seconds"] = RECENT_V2_RETENTION_SECONDS
    merged["market_feed"] = "recent_rolling_24h"
    merged["store_status"] = "ready"
    merged["ordering"] = "recent_first_pool_created_at_desc"
    merged["message"] = (
        "DexSato rolling 24h Recent feed sourced from Jupiter Recent and "
        "canonical exact WSOL pools."
    )
    return merged



class _SharedRankedExactSolResolution:
    """Request-scoped barrier that resolves live ranked token groups once."""

    _NAMES = ("trending", "top_traded", "organic_flow")

    def __init__(
        self,
        pair_group_resolver: Callable[..., dict[str, dict[str, Any]]],
    ) -> None:
        self._pair_group_resolver = pair_group_resolver
        self._lock = threading.Lock()
        self._requests: dict[
            str,
            tuple[list[Any], float, Callable[..., Any]] | None,
        ] = {}
        self._results: dict[str, dict[str, Any]] = {}
        self._error: Exception | None = None
        self._barrier = threading.Barrier(len(self._NAMES), action=self._resolve)

    def resolve(
        self,
        name: str,
        token_addresses: list[Any],
        *,
        min_liquidity_usd: float,
        request_get: Callable[..., Any],
    ) -> dict[str, Any]:
        with self._lock:
            self._requests[name] = (
                list(token_addresses),
                float(min_liquidity_usd),
                request_get,
            )
        self._barrier.wait()
        if self._error is not None:
            raise self._error
        result = self._results.get(name)
        if not isinstance(result, dict):
            raise ExactSolPairResolverUnavailable(
                "Shared exact SOL pair resolution did not return this ranked feed."
            )
        return result

    def skip(self, name: str) -> None:
        with self._lock:
            self._requests.setdefault(name, None)
        self._barrier.wait()

    def skip_if_unregistered(self, name: str) -> None:
        with self._lock:
            registered = name in self._requests
        if not registered:
            self.skip(name)

    def _resolve(self) -> None:
        with self._lock:
            active = {
                name: request
                for name, request in self._requests.items()
                if request is not None
            }
        if not active:
            return

        minimums = {request[1] for request in active.values()}
        request_gets = {id(request[2]): request[2] for request in active.values()}
        if len(minimums) != 1 or len(request_gets) != 1:
            self._error = ValueError(
                "Shared ranked resolution requires one liquidity floor and request client."
            )
            return

        groups = {
            name: request[0]
            for name, request in active.items()
        }
        try:
            self._results = self._pair_group_resolver(
                groups,
                min_liquidity_usd=next(iter(minimums)),
                request_get=next(iter(request_gets.values())),
            )
        except (
            ExactSolPairResolverUnavailable,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            self._error = error


def _shared_ranked_pair_resolver(
    shared: _SharedRankedExactSolResolution | None,
    name: str,
    default_resolver: Callable[..., dict[str, Any]],
) -> tuple[Callable[..., dict[str, Any]], Callable[[], None]]:
    if shared is None:
        return default_resolver, lambda: None

    used = False

    def resolver(
        token_addresses: list[Any],
        *,
        min_liquidity_usd: float,
        request_get: Callable[..., Any],
    ) -> dict[str, Any]:
        nonlocal used
        used = True
        return shared.resolve(
            name,
            token_addresses,
            min_liquidity_usd=min_liquidity_usd,
            request_get=request_get,
        )

    def finish() -> None:
        if not used:
            shared.skip(name)

    return resolver, finish


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


def _remember_recent_eligible_rows(
    payload: dict[str, Any],
    *,
    observed_at: float,
) -> None:
    """Remember only Recent rows that already passed live feed eligibility."""
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return

    for row in rows:
        if not isinstance(row, dict):
            continue
        mint = str(row.get("token_address") or "").strip()
        if not mint:
            continue
        _RECENT_RECENT_ELIGIBLE_ROWS[mint] = (observed_at, dict(row))


def load_recent_jupiter_recent_row(
    token_address: str,
    *,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any] | None:
    """Return a recently displayed eligible Recent row inside the grace window."""
    address = str(token_address or "").strip()
    if not address:
        return None

    now = float(now_monotonic())
    with _RECENT_MARKET_CACHE_LOCK:
        item = _RECENT_RECENT_ELIGIBLE_ROWS.get(address)
        if item is None:
            return None

        seen_at, row = item
        if (
            now < seen_at
            or (now - seen_at) >= RECENT_WORKSPACE_GRACE_SECONDS
        ):
            _RECENT_RECENT_ELIGIBLE_ROWS.pop(address, None)
            return None

        result = dict(row)
        result["recent_feed_state"] = "recent"
        result["recent_observed_age_seconds"] = max(0.0, now - seen_at)
        return result


def _normalize_recent_row(
    token: dict[str, Any],
    pair: dict[str, Any],
) -> dict[str, Any]:
    """Normalize one Jupiter Recent row without inventing a DexSato rank."""
    stats = token.get("stats1h")
    if not isinstance(stats, dict):
        stats = {}
    first_pool = token.get("firstPool")
    if not isinstance(first_pool, dict):
        first_pool = {}
    mint = str(token.get("id") or "").strip()
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
        "recent_source_position": token.get("_recent_source_position"),
        "first_pool_id": str(first_pool.get("id") or "").strip(),
        "first_pool_created_at": str(first_pool.get("createdAt") or "").strip(),
        "detected_signal": interpret_trending_signal(stats),
        "market_source": "jupiter_recent",
        "href": f"/market/recent/{mint}",
    }


def _fetch_recent(
    *,
    request_get: Callable[..., Any],
    pair_resolver: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    api_key = os.getenv("JUPITER_API_KEY", "").strip()
    if not api_key:
        return {
            "connected": False,
            "status": "not_configured",
            "message": "Recent data is unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    try:
        # Jupiter documents Recent as provider-ordered by first-pool creation.
        # No unsupported limit parameter is sent; DexSato caps what it consumes.
        response = request_get(
            JUPITER_RECENT_URL,
            headers={"x-api-key": api_key, "accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return {
            "connected": False,
            "status": "unavailable",
            "message": "Recent data is temporarily unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    if not isinstance(payload, list):
        return {
            "connected": False,
            "status": "invalid_response",
            "message": "Recent data is temporarily unavailable.",
            "rows": [],
            "raw_count": 0,
            "eligible_count": 0,
        }

    recent_tokens: list[dict[str, Any]] = []
    seen: set[str] = set()
    for position, token in enumerate(payload[:RECENT_FETCH_LIMIT], start=1):
        if not isinstance(token, dict):
            continue
        mint = str(token.get("id") or "").strip()
        if not mint or mint in seen:
            continue
        seen.add(mint)
        recent = dict(token)
        recent["_recent_source_position"] = position
        recent_tokens.append(recent)

    try:
        resolution = pair_resolver(
            [str(token.get("id") or "").strip() for token in recent_tokens],
            min_liquidity_usd=RECENT_MIN_EXACT_POOL_LIQUIDITY_USD,
            request_get=request_get,
        )
    except (ExactSolPairResolverUnavailable, RuntimeError, TypeError, ValueError):
        return {
            "connected": False,
            "status": "pair_resolution_unavailable",
            "message": "Recent exact SOL-pair resolution is temporarily unavailable.",
            "rows": [],
            "raw_count": min(len(payload), RECENT_FETCH_LIMIT),
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
    for token in recent_tokens:
        mint = str(token.get("id") or "").strip()
        pair = pair_by_mint.get(mint)
        if pair is None:
            continue
        rows.append(_normalize_recent_row(token, pair))

    return {
        "connected": True,
        "status": "live",
        "message": (
            "Jupiter Recent tokens resolved to canonical exact WSOL pools. "
            "Source order follows first-pool recency."
        ),
        "rows": rows,
        "raw_count": min(len(payload), RECENT_FETCH_LIMIT),
        "eligible_count": len(rows),
        "provider_pair_count": (
            resolution.get("provider_pair_count")
            if isinstance(resolution, dict)
            else None
        ),
        "fetch_limit": RECENT_FETCH_LIMIT,
        "display_limit": RECENT_DISPLAY_LIMIT,
        "min_liquidity_usd": RECENT_MIN_EXACT_POOL_LIQUIDITY_USD,
        "ordering": "jupiter_first_pool_recency",
    }


def load_jupiter_recent_feed(
    *,
    request_get: Callable[..., Any] = requests.get,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    now_monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Return the bounded Jupiter Recent feed with a short process cache."""
    global _RECENT_MARKET_CACHE_AT, _RECENT_MARKET_CACHE_PAYLOAD
    now = float(now_monotonic())
    with _RECENT_MARKET_CACHE_LOCK:
        if (
            _RECENT_MARKET_CACHE_PAYLOAD is not None
            and now - _RECENT_MARKET_CACHE_AT < RECENT_CACHE_SECONDS
        ):
            return dict(_RECENT_MARKET_CACHE_PAYLOAD)

    persistent = _load_recent_store_bootstrap_once()
    if persistent is not None:
        with _RECENT_MARKET_CACHE_LOCK:
            _RECENT_MARKET_CACHE_AT = now
            _RECENT_MARKET_CACHE_PAYLOAD = dict(persistent)
            _remember_recent_eligible_rows(persistent, observed_at=now)
        return dict(persistent)

    snapshot = _fetch_recent(
        request_get=request_get,
        pair_resolver=pair_resolver,
    )
    payload = _merge_recent_snapshot_into_store(snapshot)
    with _RECENT_MARKET_CACHE_LOCK:
        _RECENT_MARKET_CACHE_AT = now
        _RECENT_MARKET_CACHE_PAYLOAD = dict(payload)
        if payload.get("connected") is True:
            _remember_recent_eligible_rows(payload, observed_at=now)
    return dict(payload)


def load_jupiter_organic_flow_feed(
    *,
    request_get: Callable[..., Any] = requests.get,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    now_monotonic: Callable[[], float] = time.monotonic,
    _shared_resolution: _SharedRankedExactSolResolution | None = None,
    _refresh_outcomes: dict[str, bool] | None = None,
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
            if _shared_resolution is not None:
                _shared_resolution.skip("organic_flow")
            return dict(_ORGANIC_FLOW_CACHE_PAYLOAD)

    persistent = _load_ranked_market_bootstrap_once(
        "organic_flow",
        max_age_seconds=ORGANIC_FLOW_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
    )
    if persistent is not None:
        with _ORGANIC_FLOW_CACHE_LOCK:
            _ORGANIC_FLOW_CACHE_AT = now
            _ORGANIC_FLOW_CACHE_PAYLOAD = dict(persistent)
            _remember_organic_flow_eligible_rows(persistent, observed_at=now)
        _remember_ranked_last_good(
            "organic_flow",
            now_monotonic=now,
            existing_age_seconds=float(
                persistent.get("bootstrap_age_seconds") or 0.0
            ),
        )
        return dict(persistent)

    ranked_pair_resolver, finish_shared_resolution = _shared_ranked_pair_resolver(
        _shared_resolution,
        "organic_flow",
        pair_resolver,
    )
    payload = _fetch_organic_flow(
        request_get=request_get,
        pair_resolver=ranked_pair_resolver,
    )
    finish_shared_resolution()

    live_success = (
        payload.get("connected") is True
        and payload.get("status") == "live"
        and isinstance(payload.get("rows"), list)
    )
    if _refresh_outcomes is not None:
        with _RANKED_REFRESH_OUTCOMES_LOCK:
            _refresh_outcomes["organic_flow"] = live_success

    with _ORGANIC_FLOW_CACHE_LOCK:
        preserve_last_good = (
            not live_success
            and _ORGANIC_FLOW_CACHE_PAYLOAD is not None
            and _ranked_stale_is_servable(
                "organic_flow",
                now_monotonic=now,
                max_age_seconds=ORGANIC_FLOW_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
            )
        )
        preserved_payload = (
            dict(_ORGANIC_FLOW_CACHE_PAYLOAD) if preserve_last_good else None
        )

        if not preserve_last_good:
            _ORGANIC_FLOW_CACHE_AT = now
            _ORGANIC_FLOW_CACHE_PAYLOAD = dict(payload)

        if live_success:
            _remember_organic_flow_eligible_rows(payload, observed_at=now)

    if live_success:
        _remember_ranked_last_good(
            "organic_flow",
            now_monotonic=now,
        )

    _save_ranked_market_lkg("organic_flow", payload)

    if preserved_payload is not None:
        return preserved_payload

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
    _shared_resolution: _SharedRankedExactSolResolution | None = None,
    _refresh_outcomes: dict[str, bool] | None = None,
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
            if _shared_resolution is not None:
                _shared_resolution.skip("top_traded")
            return dict(_TOP_TRADED_CACHE_PAYLOAD)

    persistent = _load_ranked_market_bootstrap_once(
        "top_traded",
        max_age_seconds=TOP_TRADED_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
    )
    if persistent is not None:
        with _TOP_TRADED_CACHE_LOCK:
            _TOP_TRADED_CACHE_AT = now
            _TOP_TRADED_CACHE_PAYLOAD = dict(persistent)
            _remember_top_traded_eligible_rows(persistent, observed_at=now)
        _remember_ranked_last_good(
            "top_traded",
            now_monotonic=now,
            existing_age_seconds=float(
                persistent.get("bootstrap_age_seconds") or 0.0
            ),
        )
        return dict(persistent)

    ranked_pair_resolver, finish_shared_resolution = _shared_ranked_pair_resolver(
        _shared_resolution,
        "top_traded",
        pair_resolver,
    )
    payload = _fetch_top_traded(
        request_get=request_get,
        pair_resolver=ranked_pair_resolver,
    )
    finish_shared_resolution()

    live_success = (
        payload.get("connected") is True
        and payload.get("status") == "live"
        and isinstance(payload.get("rows"), list)
    )
    if _refresh_outcomes is not None:
        with _RANKED_REFRESH_OUTCOMES_LOCK:
            _refresh_outcomes["top_traded"] = live_success

    with _TOP_TRADED_CACHE_LOCK:
        preserve_last_good = (
            not live_success
            and _TOP_TRADED_CACHE_PAYLOAD is not None
            and _ranked_stale_is_servable(
                "top_traded",
                now_monotonic=now,
                max_age_seconds=TOP_TRADED_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
            )
        )
        preserved_payload = (
            dict(_TOP_TRADED_CACHE_PAYLOAD) if preserve_last_good else None
        )

        if not preserve_last_good:
            _TOP_TRADED_CACHE_AT = now
            _TOP_TRADED_CACHE_PAYLOAD = dict(payload)

        if live_success:
            _remember_top_traded_eligible_rows(payload, observed_at=now)

    if live_success:
        _remember_ranked_last_good(
            "top_traded",
            now_monotonic=now,
        )

    _save_ranked_market_lkg("top_traded", payload)

    if preserved_payload is not None:
        return preserved_payload

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
    _shared_resolution: _SharedRankedExactSolResolution | None = None,
    _refresh_outcomes: dict[str, bool] | None = None,
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
            if _shared_resolution is not None:
                _shared_resolution.skip("trending")
            return dict(_CACHE_PAYLOAD)

    persistent = _load_ranked_market_bootstrap_once(
        "trending",
        max_age_seconds=TRENDING_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
    )
    if persistent is not None:
        with _CACHE_LOCK:
            _CACHE_AT = now
            _CACHE_PAYLOAD = dict(persistent)
            _remember_eligible_rows(persistent, observed_at=now)
        _remember_ranked_last_good(
            "trending",
            now_monotonic=now,
            existing_age_seconds=float(
                persistent.get("bootstrap_age_seconds") or 0.0
            ),
        )
        return dict(persistent)

    ranked_pair_resolver, finish_shared_resolution = _shared_ranked_pair_resolver(
        _shared_resolution,
        "trending",
        pair_resolver,
    )
    payload = _fetch_trending(
        request_get=request_get,
        pair_resolver=ranked_pair_resolver,
    )
    finish_shared_resolution()

    live_success = (
        payload.get("connected") is True
        and payload.get("status") == "live"
        and isinstance(payload.get("rows"), list)
    )
    if _refresh_outcomes is not None:
        with _RANKED_REFRESH_OUTCOMES_LOCK:
            _refresh_outcomes["trending"] = live_success

    with _CACHE_LOCK:
        preserve_last_good = (
            not live_success
            and _CACHE_PAYLOAD is not None
            and _ranked_stale_is_servable(
                "trending",
                now_monotonic=now,
                max_age_seconds=TRENDING_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
            )
        )
        preserved_payload = (
            dict(_CACHE_PAYLOAD) if preserve_last_good else None
        )

        if not preserve_last_good:
            _CACHE_AT = now
            _CACHE_PAYLOAD = dict(payload)

        if live_success:
            _remember_eligible_rows(payload, observed_at=now)

    if live_success:
        _remember_ranked_last_good(
            "trending",
            now_monotonic=now,
        )

    _save_ranked_market_lkg("trending", payload)

    if preserved_payload is not None:
        return preserved_payload

    return payload


def _ranked_stale_group_snapshot(
    *,
    now_monotonic: float,
) -> dict[str, dict[str, Any]] | None:
    """Return a stale-but-servable ranked RAM group only when refresh is due."""
    specs = (
        (
            "trending",
            _CACHE_LOCK,
            "_CACHE_AT",
            "_CACHE_PAYLOAD",
            TRENDING_CACHE_SECONDS,
            TRENDING_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
        ),
        (
            "top_traded",
            _TOP_TRADED_CACHE_LOCK,
            "_TOP_TRADED_CACHE_AT",
            "_TOP_TRADED_CACHE_PAYLOAD",
            TOP_TRADED_CACHE_SECONDS,
            TOP_TRADED_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
        ),
        (
            "organic_flow",
            _ORGANIC_FLOW_CACHE_LOCK,
            "_ORGANIC_FLOW_CACHE_AT",
            "_ORGANIC_FLOW_CACHE_PAYLOAD",
            ORGANIC_FLOW_CACHE_SECONDS,
            ORGANIC_FLOW_PERSISTENT_BOOTSTRAP_MAX_AGE_SECONDS,
        ),
    )

    snapshot: dict[str, dict[str, Any]] = {}
    refresh_due = False

    for (
        name,
        lock,
        cache_at_name,
        payload_name,
        cache_seconds,
        max_age_seconds,
    ) in specs:
        with lock:
            cache_at = globals()[cache_at_name]
            payload = globals()[payload_name]

            if payload is None:
                return None

            if now_monotonic < cache_at:
                return None

            if not _ranked_stale_is_servable(
                name,
                now_monotonic=now_monotonic,
                max_age_seconds=max_age_seconds,
            ):
                return None

            if (now_monotonic - cache_at) >= cache_seconds:
                refresh_due = True

            snapshot[name] = dict(payload)

    if not refresh_due:
        return None

    return snapshot


def load_jupiter_ranked_market_feeds(
    *,
    request_get: Callable[..., Any] = requests.get,
    pair_group_resolver: Callable[..., dict[str, dict[str, Any]]] = (
        resolve_exact_sol_pair_groups
    ),
    _force_refresh: bool = False,
    _now_monotonic: Callable[[], float] = time.monotonic,
    _refresh_outcomes: dict[str, bool] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load the three $100k ranked feeds with request-scoped shared resolution."""
    if not _force_refresh:
        now = _now_monotonic()
        stale_snapshot = _ranked_stale_group_snapshot(
            now_monotonic=now,
        )

        if stale_snapshot is not None:
            if _try_begin_ranked_refresh(
                now_monotonic=now,
            ):
                def refresh_in_background() -> None:
                    failed = False

                    try:
                        refresh_outcomes: dict[str, bool] = {}
                        load_jupiter_ranked_market_feeds(
                            request_get=request_get,
                            pair_group_resolver=pair_group_resolver,
                            _force_refresh=True,
                            _now_monotonic=_now_monotonic,
                            _refresh_outcomes=refresh_outcomes,
                        )
                        failed = (
                            not refresh_outcomes
                            or not all(refresh_outcomes.values())
                        )
                    except Exception:
                        failed = True
                    finally:
                        _finish_ranked_refresh(
                            now_monotonic=_now_monotonic(),
                            failed=failed,
                        )

                try:
                    threading.Thread(
                        target=refresh_in_background,
                        name="dexsato-ranked-refresh",
                        daemon=True,
                    ).start()
                except Exception:
                    _finish_ranked_refresh(
                        now_monotonic=_now_monotonic(),
                        failed=True,
                    )

            return stale_snapshot

    shared = _SharedRankedExactSolResolution(pair_group_resolver)
    loaders = {
        "trending": load_jupiter_trending_feed,
        "top_traded": load_jupiter_top_traded_feed,
        "organic_flow": load_jupiter_organic_flow_feed,
    }

    def run(name: str, loader: Callable[..., dict[str, Any]]) -> dict[str, Any]:
        try:
            return loader(
                request_get=request_get,
                now_monotonic=_now_monotonic,
                _shared_resolution=shared,
                _refresh_outcomes=_refresh_outcomes,
            )
        except Exception:
            shared.skip_if_unregistered(name)
            raise

    with ThreadPoolExecutor(max_workers=len(loaders)) as executor:
        futures = {
            name: executor.submit(run, name, loader)
            for name, loader in loaders.items()
        }
        return {
            name: futures[name].result()
            for name in loaders
        }
