"""Quote-only Jupiter sandbox for qualified Solana Discovery tokens.

This module never requests, builds, signs or submits a transaction.  The
Jupiter order endpoint is called without a taker so the result remains a
read-only price quote.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
import math
import os
from typing import Any, Callable

import requests

from application.solana_discovery_feed_service import load_solana_discovery_feed


JUPITER_ORDER_URL = "https://api.jup.ag/swap/v2/order"
WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"
SOL_DECIMALS = 9
MIN_SOL_AMOUNT = Decimal("0.001")
MAX_SOL_AMOUNT = Decimal("100")
BASE58_ALPHABET = frozenset("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


class JupiterQuoteUnavailable(RuntimeError):
    """Raised when a safe quote cannot be returned."""


class JupiterQuoteNotConfigured(JupiterQuoteUnavailable):
    """Raised when the server has no Jupiter API key."""


def _valid_solana_address(value: str) -> bool:
    return 32 <= len(value) <= 44 and all(character in BASE58_ALPHABET for character in value)


def _amount_lamports(value: Any) -> tuple[Decimal, int]:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise ValueError("SOL amount must be a valid number.") from error
    if not amount.is_finite() or amount < MIN_SOL_AMOUNT or amount > MAX_SOL_AMOUNT:
        raise ValueError("SOL amount must be between 0.001 and 100.")
    lamports = int((amount * (10 ** SOL_DECIMALS)).to_integral_value(rounding=ROUND_DOWN))
    if lamports <= 0:
        raise ValueError("SOL amount is too small.")
    return amount, lamports


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _platform_fee(payload: dict[str, Any]) -> dict[str, Any]:
    fee = payload.get("platformFee")
    if not isinstance(fee, dict):
        return {"amount_raw": None, "fee_bps": 0, "fee_mint": None}
    return {
        "amount_raw": str(fee.get("amount")) if fee.get("amount") is not None else None,
        "fee_bps": int(_number(fee.get("feeBps")) or 0),
        "fee_mint": str(fee.get("feeMint") or "") or None,
    }


def _label(value: Any, fallback: str) -> str:
    candidate = str(value or fallback).strip()
    if not candidate or len(candidate) > 40:
        return fallback
    if not all(character.isalnum() or character in " ._-/" for character in candidate):
        return fallback
    return candidate


def fetch_jupiter_quote(
    token_address: str,
    amount_sol: Any = "0.1",
    *,
    api_key: str | None = None,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Return a bounded quote for WSOL to one qualified discovery token."""
    output_mint = str(token_address or "").strip()
    if not _valid_solana_address(output_mint):
        raise ValueError("A valid Solana token address is required.")

    public_feed = feed if feed is not None else load_solana_discovery_feed()
    candidates = public_feed.get("candidates") if isinstance(public_feed, dict) else None
    qualified = next(
        (
            candidate for candidate in candidates or []
            if isinstance(candidate, dict)
            and str(candidate.get("token_address") or "") == output_mint
        ),
        None,
    )
    if qualified is None:
        raise ValueError("Token is not a qualified Solana Discovery candidate.")

    amount, lamports = _amount_lamports(amount_sol)
    resolved_key = (api_key if api_key is not None else os.getenv("JUPITER_API_KEY", "")).strip()
    if not resolved_key:
        raise JupiterQuoteNotConfigured("Jupiter quote sandbox is not configured.")

    try:
        response = request_get(
            JUPITER_ORDER_URL,
            params={
                "inputMint": WRAPPED_SOL_MINT,
                "outputMint": output_mint,
                "amount": str(lamports),
            },
            headers={"x-api-key": resolved_key, "accept": "application/json"},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise JupiterQuoteUnavailable("Jupiter quote is temporarily unavailable.") from error

    if not isinstance(payload, dict) or payload.get("error"):
        raise JupiterQuoteUnavailable("Jupiter did not return a usable quote.")
    if payload.get("transaction") not in (None, ""):
        raise JupiterQuoteUnavailable("Quote-only policy rejected transaction material.")
    if str(payload.get("inputMint") or WRAPPED_SOL_MINT) != WRAPPED_SOL_MINT:
        raise JupiterQuoteUnavailable("Jupiter quote input mint did not match WSOL.")
    if str(payload.get("outputMint") or output_mint) != output_mint:
        raise JupiterQuoteUnavailable("Jupiter quote output mint did not match the candidate.")

    out_amount = payload.get("outAmount")
    if out_amount is None or not str(out_amount).isdigit():
        raise JupiterQuoteUnavailable("Jupiter quote has no valid output amount.")

    output_decimals = payload.get("outputDecimals")
    output_ui: str | None = None
    try:
        decimals = int(output_decimals)
        if 0 <= decimals <= 18:
            output_ui = format(Decimal(str(out_amount)) / (10 ** decimals), "f")
    except (TypeError, ValueError, InvalidOperation):
        pass

    platform_fee = _platform_fee(payload)
    return {
        "status": "QUOTE_READY",
        "quote_only": True,
        "execution_enabled": False,
        "transaction_available": False,
        "input_mint": WRAPPED_SOL_MINT,
        "output_mint": output_mint,
        "input_amount_sol": format(amount.normalize(), "f"),
        "input_amount_lamports": str(lamports),
        "output_amount_raw": str(out_amount),
        "output_amount_ui": output_ui,
        "minimum_received_raw": (
            str(payload.get("otherAmountThreshold"))
            if payload.get("otherAmountThreshold") is not None else None
        ),
        "router": _label(payload.get("router"), "Jupiter"),
        "mode": _label(payload.get("mode"), "ExactIn"),
        "price_impact_pct": _number(payload.get("priceImpactPct")),
        "slippage_bps": int(_number(payload.get("slippageBps")) or 0),
        "jupiter_fee_bps": int(_number(payload.get("feeBps")) or platform_fee["fee_bps"]),
        "jupiter_platform_fee": platform_fee,
        "dexsato_integrator_fee_bps": 0,
        "dexsato_integrator_fee_status": "NOT_CONFIGURED",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "policy": "Read-only quote; no transaction was requested, signed or submitted.",
    }
