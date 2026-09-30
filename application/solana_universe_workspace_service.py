"""Read-only Token Workspace adapter for the locked Solana Universe Core 20.

The adapter converts one canonical Core 20 mint into the existing in-memory
exact-pool feed contract used by DexSato Token Workspace services. It does not
write Discovery storage, change qualification, add a collector, or create a
second workspace implementation.
"""

from __future__ import annotations

from typing import Any, Callable

import requests

from application.dexscreener_sol_pair_resolver import (
    ExactSolPairResolverUnavailable,
    WRAPPED_SOL_MINT,
    resolve_exact_sol_pairs,
)
from application.solana_discovery_token_service import (
    load_solana_discovery_live_candles,
    load_solana_discovery_token,
    load_solana_discovery_transactions,
)
from application.solana_universe_registry import solana_universe_asset


UNIVERSE_MIN_EXACT_POOL_LIQUIDITY_USD = 0.0


class SolanaUniverseWorkspaceUnavailable(RuntimeError):
    """Raised when exact-pool evidence for a Core 20 token cannot be resolved."""


def _candidate_from_pair(
    asset: dict[str, str],
    pair: dict[str, Any],
) -> dict[str, Any] | None:
    token_address = asset["mint"]
    if str(pair.get("token_address") or "").strip() != token_address:
        return None

    # The stable Token Workspace live-pair reader currently expects the token
    # on the base side of an exact token/WSOL pool. Preserve that contract here
    # instead of silently widening shared workspace semantics.
    if str(pair.get("token_side") or "").strip() != "base":
        return None

    pair_address = str(pair.get("pair_address") or "").strip()
    if not pair_address:
        return None

    return {
        "token_address": token_address,
        "pair_address": pair_address,
        "symbol": asset["symbol"],
        "name": asset["name"],
        "quote_symbol": "SOL",
        "quote_address": WRAPPED_SOL_MINT,
        "dex_id": str(pair.get("dex_id") or "").strip(),
        "price_usd": pair.get("price_usd"),
        "liquidity_usd": pair.get("liquidity_usd"),
        "volume_24h_usd": pair.get("volume_h24_usd"),
        "change_24h": pair.get("price_change_h24"),
        "source_url": f"https://dexscreener.com/solana/{pair_address}",
        "evidence": (
            "Canonical Solana Universe asset resolved to its highest-liquidity "
            "exact token/WSOL pool."
        ),
        "risk_label": (
            "Universe membership is curated identity coverage, not token "
            "qualification or a safety guarantee"
        ),
        "currently_qualified": False,
        "workspace_source": "DexSato Solana Universe",
        "workspace_kind": "solana-universe",
    }


def load_solana_universe_execution_feed(
    token_address: str,
    *,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Resolve one Core 20 mint into the existing exact-pool feed contract."""
    address = str(token_address or "").strip()
    asset = solana_universe_asset(address)

    if asset is None:
        return {
            "candidates": [],
            "updated_label": "Solana Universe",
            "market_feed": "solana_universe",
            "source": "core20-canonical-registry",
        }

    try:
        resolved = pair_resolver(
            [address],
            min_liquidity_usd=UNIVERSE_MIN_EXACT_POOL_LIQUIDITY_USD,
            request_get=request_get,
        )
    except ExactSolPairResolverUnavailable as error:
        raise SolanaUniverseWorkspaceUnavailable(
            "Solana Universe exact-pool resolution is temporarily unavailable."
        ) from error

    rows = resolved.get("rows") if isinstance(resolved, dict) else None
    pair = next(
        (
            row
            for row in rows or []
            if isinstance(row, dict)
            and str(row.get("token_address") or "").strip() == address
        ),
        None,
    )
    candidate = _candidate_from_pair(asset, pair) if isinstance(pair, dict) else None

    return {
        "candidates": [candidate] if candidate is not None else [],
        "updated_label": "Solana Universe Â· Core 20",
        "market_feed": "solana_universe",
        "source": "core20-canonical-registry+exact-wsol",
    }


def load_solana_universe_execution_record(
    token_address: str,
    *,
    feed: dict[str, Any] | None = None,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    """Return one Core 20 execution record from a supplied or resolved feed."""
    address = str(token_address or "").strip()
    active_feed = (
        feed
        if isinstance(feed, dict)
        else load_solana_universe_execution_feed(
            address,
            pair_resolver=pair_resolver,
            request_get=request_get,
        )
    )

    return next(
        (
            candidate
            for candidate in active_feed.get("candidates") or []
            if isinstance(candidate, dict)
            and str(candidate.get("token_address") or "").strip() == address
        ),
        None,
    )


def is_solana_universe_workspace_eligible(
    token_address: str,
    *,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    request_get: Callable[..., Any] = requests.get,
) -> bool:
    """Require canonical Core 20 membership plus a compatible exact WSOL pool."""
    return (
        load_solana_universe_execution_record(
            token_address,
            pair_resolver=pair_resolver,
            request_get=request_get,
        )
        is not None
    )


def load_solana_universe_token_workspace(
    token_address: str,
    *,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    request_get: Callable[..., Any] = requests.get,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Reuse the stable Token Workspace read model for one Core 20 token."""
    address = str(token_address or "").strip()
    feed = load_solana_universe_execution_feed(
        address,
        pair_resolver=pair_resolver,
        request_get=request_get,
    )
    detail = load_solana_discovery_token(
        address,
        feed=feed,
        request_get=request_get,
    )
    if detail is None:
        return None

    detail["workspace_kind"] = "solana-universe"
    detail["workspace_source"] = "DexSato Solana Universe Â· Core 20"
    detail["quote_label"] = (
        "Live exact-pool observation"
        if detail.get("quote_status") == "LIVE"
        else "Solana Universe exact-pool observation"
    )
    return detail, feed


def load_solana_universe_live_candles(
    token_address: str,
    timeframe: str,
    *,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    """Reuse the existing exact-pool candle service with a Universe feed."""
    feed = load_solana_universe_execution_feed(
        token_address,
        pair_resolver=pair_resolver,
        request_get=request_get,
    )
    return load_solana_discovery_live_candles(
        token_address,
        timeframe,
        feed=feed,
        request_get=request_get,
    )


def load_solana_universe_transactions(
    token_address: str,
    *,
    pair_resolver: Callable[..., dict[str, Any]] = resolve_exact_sol_pairs,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    """Reuse the existing exact-pool transaction service with a Universe feed."""
    feed = load_solana_universe_execution_feed(
        token_address,
        pair_resolver=pair_resolver,
        request_get=request_get,
    )
    return load_solana_discovery_transactions(
        token_address,
        feed=feed,
        request_get=request_get,
    )