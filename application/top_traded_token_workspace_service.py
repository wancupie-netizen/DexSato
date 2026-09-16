"""Top Traded market-feed Token Workspace read model.

Top Traded is separate from the DexSato Discovery archive. This module reuses
stable exact-pool read services without creating, qualifying, or persisting
Discovery records.
"""

from __future__ import annotations

from typing import Any, Callable

import requests

from application.jupiter_market_feed_service import (
    load_jupiter_top_traded_feed,
    load_recent_jupiter_top_traded_row,
)
from application.solana_discovery_token_service import (
    load_solana_discovery_live_candles,
    load_solana_discovery_token,
    load_solana_discovery_transactions,
)


class TopTradedWorkspaceUnavailable(RuntimeError):
    """Raised when the Top Traded market feed cannot be resolved."""


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
        "top_traded_rank": row.get("top_traded_rank"),
        "token_image_url": str(row.get("icon") or "").strip(),
        "source_url": f"https://dexscreener.com/solana/{pair_address}",
        "evidence": (
            "Jupiter Top Traded · 24H token resolved to a canonical exact "
            "token/WSOL pool with the DexSato market-feed liquidity floor."
        ),
        "risk_label": (
            "Top Traded status and exact-pool liquidity are market "
            "observations, not token qualification or a safety guarantee"
        ),
        "currently_qualified": False,
        "workspace_source": "Jupiter Top Traded · 24H",
        "workspace_kind": "top-traded",
    }


def load_top_traded_candidate_feed(
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_top_traded_feed,
) -> dict[str, Any]:
    """Build an in-memory feed from current eligible Top Traded rows."""
    market = market_loader()
    if not isinstance(market, dict) or market.get("connected") is not True:
        raise TopTradedWorkspaceUnavailable(
            "Top Traded market feed is temporarily unavailable."
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
        "updated_label": "Jupiter Top Traded · 24H",
        "market_feed": "top-traded",
        "source": "jupiter-toptraded-24h",
    }


def _load_top_traded_feed_for_token(
    token_address: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_top_traded_feed,
) -> dict[str, Any]:
    """Use live eligibility first, then bounded recently-displayed continuity."""
    feed = load_top_traded_candidate_feed(market_loader=market_loader)
    address = str(token_address or "").strip()

    candidates = feed.get("candidates")
    if not isinstance(candidates, list):
        candidates = []

    if any(
        isinstance(candidate, dict)
        and str(candidate.get("token_address") or "").strip() == address
        for candidate in candidates
    ):
        return feed

    recent_row = load_recent_jupiter_top_traded_row(address)
    if recent_row is None:
        return feed

    recent_candidate = _candidate_from_row(recent_row)
    if recent_candidate is None:
        return feed

    augmented = dict(feed)
    augmented["candidates"] = [*candidates, recent_candidate]
    augmented["workspace_continuity"] = "recently-observed"
    return augmented


def load_top_traded_execution_feed(
    token_address: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_top_traded_feed,
) -> dict[str, Any]:
    """Return the bounded Top Traded feed used by execution routes."""
    return _load_top_traded_feed_for_token(
        token_address,
        market_loader=market_loader,
    )


def load_top_traded_execution_record(
    token_address: str,
    *,
    feed: dict[str, Any] | None = None,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_top_traded_feed,
) -> dict[str, Any] | None:
    """Return one candidate from the bounded Top Traded execution feed."""
    address = str(token_address or "").strip()
    active_feed = (
        feed
        if isinstance(feed, dict)
        else _load_top_traded_feed_for_token(
            address,
            market_loader=market_loader,
        )
    )
    candidates = active_feed.get("candidates")
    if not isinstance(candidates, list):
        return None

    for candidate in candidates:
        if (
            isinstance(candidate, dict)
            and str(candidate.get("token_address") or "").strip() == address
        ):
            return candidate
    return None


def is_top_traded_token_workspace_eligible(
    token_address: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_top_traded_feed,
) -> bool:
    """Validate live or recently displayed Top Traded eligibility."""
    feed = _load_top_traded_feed_for_token(
        token_address,
        market_loader=market_loader,
    )
    address = str(token_address or "").strip()
    candidates = feed.get("candidates")
    if not isinstance(candidates, list):
        return False

    return any(
        isinstance(candidate, dict)
        and str(candidate.get("token_address") or "").strip() == address
        for candidate in candidates
    )


def load_top_traded_token_workspace(
    token_address: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_top_traded_feed,
    request_get: Callable[..., Any] = requests.get,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return one Top Traded workspace without touching Discovery storage."""
    feed = _load_top_traded_feed_for_token(
        token_address,
        market_loader=market_loader,
    )
    address = str(token_address or "").strip()

    detail = load_solana_discovery_token(
        address,
        feed=feed,
        request_get=request_get,
    )
    if detail is None:
        return None

    detail["workspace_kind"] = "top-traded"
    detail["workspace_source"] = "Jupiter Top Traded · 24H"
    detail["quote_label"] = (
        "Live exact-pool observation"
        if detail.get("quote_status") == "LIVE"
        else "Top Traded exact-pool observation"
    )
    return detail, feed


def load_top_traded_live_candles(
    token_address: str,
    timeframe: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_top_traded_feed,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    feed = _load_top_traded_feed_for_token(
        token_address,
        market_loader=market_loader,
    )
    return load_solana_discovery_live_candles(
        token_address,
        timeframe,
        feed=feed,
        request_get=request_get,
    )


def load_top_traded_transactions(
    token_address: str,
    *,
    market_loader: Callable[..., dict[str, Any]] = load_jupiter_top_traded_feed,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any] | None:
    feed = _load_top_traded_feed_for_token(
        token_address,
        market_loader=market_loader,
    )
    return load_solana_discovery_transactions(
        token_address,
        feed=feed,
        request_get=request_get,
    )
