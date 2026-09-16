"""Trending market-feed Token Workspace read model.

Trending is intentionally separate from the DexSato Discovery archive.
This module reuses stable exact-pool read services without creating,
qualifying, or persisting Discovery records.
"""

from __future__ import annotations

from typing import Any, Callable

import requests

from application.jupiter_market_feed_service import load_jupiter_trending_feed
from application.solana_discovery_token_service import (
    load_solana_discovery_live_candles,
    load_solana_discovery_token,
    load_solana_discovery_transactions,
)


class TrendingWorkspaceUnavailable(RuntimeError):
    """Raised when the live Trending market feed cannot be resolved."""


def _candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    token_address = str(row.get("token_address") or "").strip()
    pair_address = str(row.get("pair_address") or "").strip()
    if not token_address or not pair_address:
        return None

    dex_id = str(row.get("dex_id") or "").strip()
    symbol = str(row.get("symbol") or "Unknown").strip()
    name = str(row.get("name") or "Unknown token").strip()

    return {
        "token_address": token_address,
        "pair_address": pair_address,
        "symbol": symbol,
        "name": name,
        "quote_symbol": "SOL",
        "quote_address": str(row.get("quote_address") or "").strip(),
        "dex_id": dex_id,
        "price_usd": row.get("price_usd"),
        "liquidity_usd": row.get("liquidity_usd"),
        "change_1h": row.get("change_1h"),
        "volume_1h_usd": row.get("volume_1h_usd"),
        "trending_rank": row.get("trending_rank"),
        "token_image_url": str(row.get("icon") or "").strip(),
        "source_url": f"https://dexscreener.com/solana/{pair_address}",
        "evidence": (
            "Jupiter Top Trending · 1H token resolved to a canonical exact "
            "token/WSOL pool with the DexSato market-feed liquidity floor."
        ),
        "risk_label": (
            "Trending status and exact-pool liquidity are market observations, "
            "not token qualification or a safety guarantee"
        ),
        "currently_qualified": False,
        "workspace_source": "Jupiter Top Trending · 1H",
        "workspace_kind": "trending",
    }


def load_trending_candidate_feed(
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_trending_feed,
) -> dict[str, Any]:
    """Build an in-memory feed from current eligible Trending rows only."""
    market = market_loader()
    if not isinstance(market, dict) or market.get("connected") is not True:
        raise TrendingWorkspaceUnavailable(
            "Trending market feed is temporarily unavailable."
        )

    rows = market.get("rows")
    if not isinstance(rows, list):
        rows = []

    candidates: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate = _candidate_from_row(row)
        if candidate is not None:
            candidates.append(candidate)

    return {
        "candidates": candidates,
        "updated_label": "Jupiter Trending · 1H",
        "market_feed": "trending",
        "source": "jupiter-toptrending-1h",
    }


def load_trending_token_workspace(
    token_address: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_trending_feed,
    request_get: Callable[..., Any] = requests.get,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return one live Trending workspace without touching Discovery storage."""
    feed = load_trending_candidate_feed(market_loader=market_loader)
    address = str(token_address or "").strip()

    detail = load_solana_discovery_token(
        address,
        feed=feed,
        request_get=request_get,
    )
    if detail is None:
        return None

    detail["workspace_kind"] = "trending"
    detail["workspace_source"] = "Jupiter Top Trending · 1H"
    detail["quote_label"] = (
        "Live exact-pool observation"
        if detail.get("quote_status") == "LIVE"
        else "Trending exact-pool observation"
    )
    return detail, feed


def load_trending_live_candles(
    token_address: str,
    timeframe: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_trending_feed,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    feed = load_trending_candidate_feed(market_loader=market_loader)
    return load_solana_discovery_live_candles(
        token_address,
        timeframe,
        feed=feed,
        request_get=request_get,
    )


def load_trending_transactions(
    token_address: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_trending_feed,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    feed = load_trending_candidate_feed(market_loader=market_loader)
    return load_solana_discovery_transactions(
        token_address,
        feed=feed,
        request_get=request_get,
    )
