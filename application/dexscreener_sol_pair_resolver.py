"""Read-only exact WSOL-pair resolver for Solana market feeds.

This module does not write Discovery archive data and does not change
qualification, engine, swap, referral, collector, or storage semantics.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

import requests


DEXSCREENER_TOKENS_URL = (
    "https://api.dexscreener.com/tokens/v1/solana/{token_addresses}"
)
SOLANA_CHAIN_ID = "solana"
WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"
MAX_TOKEN_ADDRESSES = 50
DEXSCREENER_BATCH_SIZE = 30
REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_MIN_LIQUIDITY_USD = 100_000.0

_SOLANA_ADDRESS_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class ExactSolPairResolverUnavailable(RuntimeError):
    """Raised when DEX Screener cannot provide a valid resolver response."""


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _normalize_token_addresses(values: Iterable[Any]) -> list[str]:
    """Return unique valid Solana addresses in caller order, bounded to 50."""
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        address = str(value or "").strip()
        if not address or address == WRAPPED_SOL_MINT:
            continue
        if not _SOLANA_ADDRESS_RE.fullmatch(address):
            continue
        if address in seen:
            continue
        seen.add(address)
        result.append(address)
        if len(result) >= MAX_TOKEN_ADDRESSES:
            break

    return result


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def _pair_for_token(
    pair: Any,
    token_address: str,
    *,
    min_liquidity_usd: float,
) -> dict[str, Any] | None:
    """Normalize one exact token/WSOL pair when it satisfies liquidity."""
    if not isinstance(pair, dict):
        return None
    if str(pair.get("chainId") or "").strip().lower() != SOLANA_CHAIN_ID:
        return None

    pair_address = str(pair.get("pairAddress") or "").strip()
    dex_id = str(pair.get("dexId") or "").strip()
    base = pair.get("baseToken")
    quote = pair.get("quoteToken")
    if not pair_address or not isinstance(base, dict) or not isinstance(quote, dict):
        return None

    base_address = str(base.get("address") or "").strip()
    quote_address = str(quote.get("address") or "").strip()

    if base_address == token_address and quote_address == WRAPPED_SOL_MINT:
        token_side = "base"
    elif quote_address == token_address and base_address == WRAPPED_SOL_MINT:
        token_side = "quote"
    else:
        return None

    liquidity = pair.get("liquidity")
    liquidity_usd = (
        _number(liquidity.get("usd"))
        if isinstance(liquidity, dict)
        else None
    )
    if liquidity_usd is None or liquidity_usd < min_liquidity_usd:
        return None

    volume = pair.get("volume")
    price_change = pair.get("priceChange")
    txns = pair.get("txns")

    return {
        "token_address": token_address,
        "pair_address": pair_address,
        "dex_id": dex_id,
        "token_side": token_side,
        "base_address": base_address,
        "base_symbol": str(base.get("symbol") or "").strip(),
        "quote_address": quote_address,
        "quote_symbol": str(quote.get("symbol") or "").strip(),
        "liquidity_usd": liquidity_usd,
        "price_usd": _number(pair.get("priceUsd")),
        "volume_h24_usd": (
            _number(volume.get("h24")) if isinstance(volume, dict) else None
        ),
        "price_change_h24": (
            _number(price_change.get("h24"))
            if isinstance(price_change, dict)
            else None
        ),
        "txns_h24": (
            dict(txns.get("h24"))
            if isinstance(txns, dict) and isinstance(txns.get("h24"), dict)
            else None
        ),
        "pair_created_at": pair.get("pairCreatedAt"),
        "source": "dexscreener",
    }


def _fetch_pairs(
    token_addresses: list[str],
    *,
    request_get: Callable[..., Any],
) -> list[dict[str, Any]]:
    """Fetch DEX Screener pairs in <=30-address batches."""
    all_pairs: list[dict[str, Any]] = []

    for batch in _chunks(token_addresses, DEXSCREENER_BATCH_SIZE):
        endpoint = DEXSCREENER_TOKENS_URL.format(
            token_addresses=",".join(batch)
        )
        try:
            response = request_get(
                endpoint,
                headers={"accept": "application/json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
            raise ExactSolPairResolverUnavailable(
                "DEX Screener exact SOL pair resolution is temporarily unavailable."
            ) from error

        if not isinstance(payload, list):
            raise ExactSolPairResolverUnavailable(
                "DEX Screener exact SOL pair response is invalid."
            )

        for pair in payload:
            if isinstance(pair, dict):
                all_pairs.append(pair)

    return all_pairs


def resolve_exact_sol_pairs(
    token_addresses: Iterable[Any],
    *,
    min_liquidity_usd: float = DEFAULT_MIN_LIQUIDITY_USD,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Resolve the highest-liquidity canonical WSOL pair for each input token.

    Input order is preserved. Only exact token/WSOL pairs at or above the
    requested liquidity floor are eligible. No data is persisted.
    """
    minimum = _number(min_liquidity_usd)
    if minimum is None or minimum < 0:
        raise ValueError("min_liquidity_usd must be a non-negative finite number.")

    addresses = _normalize_token_addresses(token_addresses)
    if not addresses:
        return {
            "status": "ok",
            "requested_count": 0,
            "provider_pair_count": 0,
            "resolved_count": 0,
            "min_liquidity_usd": float(minimum),
            "rows": [],
        }

    provider_pairs = _fetch_pairs(addresses, request_get=request_get)

    requested = set(addresses)
    best_by_token: dict[str, dict[str, Any]] = {}

    for pair in provider_pairs:
        base = pair.get("baseToken")
        quote = pair.get("quoteToken")
        if not isinstance(base, dict) or not isinstance(quote, dict):
            continue

        base_address = str(base.get("address") or "").strip()
        quote_address = str(quote.get("address") or "").strip()

        candidates: list[str] = []
        if base_address in requested:
            candidates.append(base_address)
        if quote_address in requested and quote_address != base_address:
            candidates.append(quote_address)

        for token_address in candidates:
            normalized = _pair_for_token(
                pair,
                token_address,
                min_liquidity_usd=float(minimum),
            )
            if normalized is None:
                continue

            previous = best_by_token.get(token_address)
            if (
                previous is None
                or float(normalized["liquidity_usd"])
                > float(previous["liquidity_usd"])
            ):
                best_by_token[token_address] = normalized

    rows = [
        best_by_token[address]
        for address in addresses
        if address in best_by_token
    ]

    return {
        "status": "ok",
        "requested_count": len(addresses),
        "provider_pair_count": len(provider_pairs),
        "resolved_count": len(rows),
        "min_liquidity_usd": float(minimum),
        "rows": rows,
    }
