"""Trading venue discovery for the Founder dashboard.

This service is presentation enrichment only. It does not influence market
selection, observations, signals, confidence, or decisions.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from scanner.market_registry import get_market


TOKEN_PAIRS_URL = (
    "https://api.dexscreener.com/token-pairs/v1/"
    "{chain_id}/{token_address}"
)

MAX_TRADING_VENUES = 3

_DEX_NAMES = {
    "cetus": "Cetus",
    "orca": "Orca",
    "pancakeswap": "PancakeSwap",
    "raydium": "Raydium",
    "sushiswap": "SushiSwap",
    "uniswap": "Uniswap",
}


def _same(value: object, expected: object) -> bool:
    return str(value).strip().casefold() == str(expected).strip().casefold()


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _venue_name(dex_id: object) -> str:
    normalized = str(dex_id or "").strip().lower()
    if not normalized:
        return "Unknown DEX"
    return _DEX_NAMES.get(normalized, normalized.replace("-", " ").title())


def rank_trading_venues(
    *,
    pairs: object,
    market: dict[str, object],
    limit: int = MAX_TRADING_VENUES,
) -> list[dict[str, object]]:
    """Return verified same-market DEX venues ranked by 24h volume."""
    if not isinstance(pairs, list):
        return []

    display_pair = str(market["display_pair"]).strip().upper()
    _, quote_symbol = display_pair.split("/", 1)
    candidates: list[dict[str, object]] = []

    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        base = pair.get("baseToken", {})
        quote = pair.get("quoteToken", {})
        if not isinstance(base, dict) or not isinstance(quote, dict):
            continue
        if not _same(pair.get("chainId"), market["chain_id"]):
            continue
        if not _same(base.get("address"), market["base_address"]):
            continue
        if not _same(quote.get("symbol"), quote_symbol):
            continue

        volume = pair.get("volume", {})
        liquidity = pair.get("liquidity", {})
        volume_24h = volume.get("h24") if isinstance(volume, dict) else None
        liquidity_usd = liquidity.get("usd") if isinstance(liquidity, dict) else None
        dex_id = str(pair.get("dexId") or "").strip().lower()
        if not dex_id:
            continue

        candidates.append(
            {
                "name": _venue_name(dex_id),
                "dex_id": dex_id,
                "type": "DEX",
                "pair": display_pair,
                "chain": str(pair.get("chainId") or ""),
                "volume_24h": volume_24h,
                "liquidity": liquidity_usd,
                "url": pair.get("url"),
                "source": "DexScreener",
            }
        )

    candidates.sort(
        key=lambda item: (
            _number(item["volume_24h"]),
            _number(item["liquidity"]),
        ),
        reverse=True,
    )

    # Keep the strongest pool for each DEX so the list represents venues,
    # rather than several pools belonging to the same venue.
    ranked: list[dict[str, object]] = []
    seen: set[str] = set()
    for candidate in candidates:
        dex_id = str(candidate["dex_id"])
        if dex_id in seen:
            continue
        seen.add(dex_id)
        ranked.append(candidate)
        if len(ranked) >= max(1, limit):
            break

    return ranked


def fetch_trading_venues(
    token: str,
    *,
    request_get: Callable[..., Any] | None = None,
) -> list[dict[str, object]]:
    """Fetch and rank DEX venues for one registered DexSato market."""
    if request_get is None:
        import requests

        request_get = requests.get

    market = get_market(token)
    response = request_get(
        TOKEN_PAIRS_URL.format(
            chain_id=market["chain_id"],
            token_address=market["base_address"],
        ),
        timeout=15,
    )
    response.raise_for_status()
    return rank_trading_venues(
        pairs=response.json(),
        market=market,
    )
