"""Quote-only Jupiter sandbox for observed Solana Discovery tokens.

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

from application.solana_discovery_feed_service import load_solana_discovery_record
from application.jupiter_fee_policy import (
    FeePolicyConfigurationError, FeePolicyRejected, get_fee_policy, validate_fee_response,
)
from application.jupiter_fee_disclosure import build_fee_disclosure
from application.jupiter_referral_verification import ReferralVerificationError


JUPITER_ORDER_URL = "https://api.jup.ag/swap/v2/order"
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"
SOL_DECIMALS = 9
MIN_SOL_AMOUNT = Decimal("0.001")
MAX_SOL_AMOUNT = Decimal("100")
MAX_INPUT_RAW = 18_446_744_073_709_551_615
BASE58_ALPHABET = frozenset("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


class JupiterQuoteUnavailable(RuntimeError):
    """Raised when a safe quote cannot be returned."""


class JupiterQuoteNotConfigured(JupiterQuoteUnavailable):
    """Raised when the server has no Jupiter API key."""


def _fee_policy():
    try:
        return get_fee_policy()
    except FeePolicyConfigurationError as error:
        raise JupiterQuoteNotConfigured("Jupiter fee policy is not configured correctly.") from error


def _fee_evidence(policy, payload, input_mint, output_mint):
    try:
        return validate_fee_response(
            policy, payload, input_mint=input_mint, output_mint=output_mint,
        )
    except FeePolicyRejected as error:
        raise JupiterQuoteUnavailable("Jupiter referral fee could not be verified.") from error


def _fee_disclosure(evidence, payload, input_raw, input_mint, output_mint=None):
    try:
        return build_fee_disclosure(
            evidence, payload, input_raw, output_mint, input_mint=input_mint,
        )
    except (ReferralVerificationError, FeePolicyRejected) as error:
        raise JupiterQuoteUnavailable("Jupiter referral account verification is unavailable.") from error


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


def _trade_direction(value: Any) -> str:
    side = str(value or "buy").strip().lower()
    if side not in {"buy", "sell"}:
        raise ValueError("Trade side must be buy or sell.")
    return side


def _amount_token_units(value: Any, decimals: int) -> tuple[Decimal, int]:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise ValueError("Token amount must be a valid number.") from error
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Token amount must be greater than zero.")
    raw = int((amount * (Decimal(10) ** decimals)).to_integral_value(rounding=ROUND_DOWN))
    if raw <= 0:
        raise ValueError("Token amount is smaller than one base unit.")
    if raw > MAX_INPUT_RAW:
        raise ValueError("Token amount exceeds the supported swap limit.")
    return amount, raw


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


def _token_decimals(
    mint: str,
    provider_value: Any,
    *,
    rpc_url: str | None,
    request_post: Callable[..., Any],
) -> tuple[int | None, str | None]:
    """Resolve token decimals, preferring a valid provider value then Solana RPC."""
    try:
        decimals = int(provider_value)
        if 0 <= decimals <= 18:
            return decimals, "Jupiter"
    except (TypeError, ValueError):
        pass

    endpoint = (rpc_url or os.getenv("SOLANA_RPC_URL", "") or SOLANA_RPC_URL).strip()
    try:
        response = request_post(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenSupply",
                "params": [mint],
            },
            headers={"accept": "application/json", "content-type": "application/json"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        value = payload.get("result", {}).get("value", {}) if isinstance(payload, dict) else {}
        decimals = int(value.get("decimals"))
        if 0 <= decimals <= 18:
            return decimals, "Solana mint"
    except (requests.RequestException, RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return None, None


def _raw_to_ui(value: Any, decimals: int | None) -> str | None:
    if decimals is None or value is None or not str(value).isdigit():
        return None
    try:
        return format(Decimal(str(value)) / (Decimal(10) ** decimals), "f")
    except (InvalidOperation, ValueError):
        return None


def fetch_jupiter_quote(
    token_address: str,
    amount_sol: Any = "0.1",
    *,
    side: str = "buy",
    api_key: str | None = None,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
    request_post: Callable[..., Any] = requests.post,
    rpc_url: str | None = None,
) -> dict[str, Any]:
    """Return a bounded two-way quote for one observed discovery token."""
    token_mint = str(token_address or "").strip()
    if not _valid_solana_address(token_mint):
        raise ValueError("A valid Solana token address is required.")

    if feed is None:
        observed = load_solana_discovery_record(token_mint)
    else:
        candidates = feed.get("candidates") if isinstance(feed, dict) else None
        observed = next(
            (
                candidate for candidate in candidates or []
                if isinstance(candidate, dict)
                and str(candidate.get("token_address") or "") == token_mint
            ),
            None,
        )
    if observed is None:
        raise ValueError("Token is not an observed Solana Discovery token.")

    direction = _trade_direction(side)
    if direction == "buy":
        amount, input_raw = _amount_lamports(amount_sol)
        input_mint = WRAPPED_SOL_MINT
        output_mint = token_mint
        input_decimals = SOL_DECIMALS
        input_decimals_source = "Solana protocol"
    else:
        input_decimals, input_decimals_source = _token_decimals(
            token_mint, None, rpc_url=rpc_url, request_post=request_post,
        )
        if input_decimals is None:
            raise JupiterQuoteUnavailable("Token decimals are unavailable for a sell quote.")
        amount, input_raw = _amount_token_units(amount_sol, input_decimals)
        input_mint = token_mint
        output_mint = WRAPPED_SOL_MINT
    resolved_key = (api_key if api_key is not None else os.getenv("JUPITER_API_KEY", "")).strip()
    if not resolved_key:
        raise JupiterQuoteNotConfigured("Jupiter quote sandbox is not configured.")

    fee_policy = _fee_policy()

    try:
        response = request_get(
            JUPITER_ORDER_URL,
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(input_raw),
                "excludeRouters": "jupiterz,dflow,okx",
                **fee_policy.request_parameters(),
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
    fee_evidence = _fee_evidence(fee_policy, payload, input_mint, output_mint)
    fee_disclosure = _fee_disclosure(
        fee_evidence, payload, input_raw, input_mint, output_mint,
    )
    if payload.get("transaction") not in (None, ""):
        raise JupiterQuoteUnavailable("Quote-only policy rejected transaction material.")
    if str(payload.get("inputMint") or input_mint) != input_mint:
        raise JupiterQuoteUnavailable("Jupiter quote input mint did not match the trade side.")
    if str(payload.get("outputMint") or output_mint) != output_mint:
        raise JupiterQuoteUnavailable("Jupiter quote output mint did not match the candidate.")

    out_amount = payload.get("outAmount")
    if out_amount is None or not str(out_amount).isdigit():
        raise JupiterQuoteUnavailable("Jupiter quote has no valid output amount.")

    if output_mint == WRAPPED_SOL_MINT:
        decimals, decimals_source = SOL_DECIMALS, "Solana protocol"
    else:
        decimals, decimals_source = _token_decimals(
            output_mint,
            payload.get("outputDecimals"),
            rpc_url=rpc_url,
            request_post=request_post,
        )
    output_ui = _raw_to_ui(out_amount, decimals)
    minimum_raw = (
        str(payload.get("otherAmountThreshold"))
        if payload.get("otherAmountThreshold") is not None else None
    )

    platform_fee = _platform_fee(payload)
    return {
        "status": "QUOTE_READY",
        "quote_only": True,
        "execution_enabled": False,
        "transaction_available": False,
        "side": direction,
        "token_mint": token_mint,
        "input_mint": input_mint,
        "output_mint": output_mint,
        "input_amount_ui": format(amount.normalize(), "f"),
        "input_amount_raw": str(input_raw),
        "input_decimals": input_decimals,
        "input_decimals_source": input_decimals_source,
        "input_amount_sol": format(amount.normalize(), "f") if direction == "buy" else None,
        "input_amount_lamports": str(input_raw) if direction == "buy" else None,
        "output_amount_raw": str(out_amount),
        "output_amount_ui": output_ui,
        "output_decimals": decimals,
        "output_decimals_source": decimals_source,
        "minimum_received_raw": minimum_raw,
        "minimum_received_ui": _raw_to_ui(minimum_raw, decimals),
        "router": _label(payload.get("router"), "Jupiter"),
        "mode": _label(payload.get("mode"), "ExactIn"),
        "price_impact_pct": _number(payload.get("priceImpactPct")),
        "slippage_bps": int(_number(payload.get("slippageBps")) or 0),
        "jupiter_fee_bps": int(_number(payload.get("feeBps")) or platform_fee["fee_bps"]),
        "jupiter_platform_fee": platform_fee,
        **fee_evidence.public_fields(),
        "fee_disclosure": fee_disclosure,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "policy": "Read-only quote; no transaction was requested, signed or submitted.",
    }
