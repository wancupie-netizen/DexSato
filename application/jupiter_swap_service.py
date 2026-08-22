"""Controlled, non-custodial Jupiter execution for qualified discovery tokens.

Only unsigned provider transactions and user-approved signed transactions pass
through this service. Wallet keys, seed phrases, and funds never enter DexSato.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import os
import re
import threading
from typing import Any, Callable

import requests

from application.jupiter_quote_service import (
    BASE58_ALPHABET,
    JUPITER_ORDER_URL,
    WRAPPED_SOL_MINT,
    JupiterQuoteNotConfigured,
    JupiterQuoteUnavailable,
    _amount_lamports,
    _label,
    _number,
    _platform_fee,
    _valid_solana_address,
)
from application.solana_discovery_feed_service import load_solana_discovery_feed


JUPITER_EXECUTE_URL = "https://api.jup.ag/swap/v2/execute"
ORDER_LIFETIME_SECONDS = 120
MAX_PENDING_ORDERS = 256
MAX_TRANSACTION_BYTES = 4096
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
BASE58_DIGITS = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


@dataclass(slots=True)
class _PendingOrder:
    token_address: str
    wallet_address: str
    expires_at: datetime
    message_digest: bytes
    wallet_signature_index: int
    last_valid_block_height: str | None
    signed_digest: bytes | None = None
    executing: bool = False
    completed: bool = False


_pending_orders: dict[str, _PendingOrder] = {}
_pending_lock = threading.RLock()


class JupiterSwapRejected(ValueError):
    """Raised when an order or signed transaction violates the D6 policy."""


class JupiterSwapExpired(JupiterSwapRejected):
    """Raised when an order is unknown, expired, or already completed."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _api_key(value: str | None) -> str:
    key = (value if value is not None else os.getenv("JUPITER_API_KEY", "")).strip()
    if not key:
        raise JupiterQuoteNotConfigured("Jupiter swap execution is not configured.")
    return key


def _base58_bytes(address: str) -> bytes:
    if not _valid_solana_address(address):
        raise JupiterSwapRejected("A valid connected Solana wallet address is required.")
    number = 0
    for character in address:
        number = number * 58 + BASE58_DIGITS.index(character)
    encoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    raw = b"\x00" * (len(address) - len(address.lstrip("1"))) + encoded
    if len(raw) != 32:
        raise JupiterSwapRejected("A valid connected Solana wallet address is required.")
    return raw


def _shortvec(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 21, 7):
        if offset >= len(data):
            raise JupiterSwapRejected("Jupiter returned an invalid Solana transaction.")
        current = data[offset]
        offset += 1
        value |= (current & 0x7F) << shift
        if current < 128:
            return value, offset
    raise JupiterSwapRejected("Jupiter returned an invalid Solana transaction.")


def _transaction_parts(value: Any) -> tuple[bytes, list[bytes], bytes, list[bytes]]:
    if not isinstance(value, str) or not value or len(value) > MAX_TRANSACTION_BYTES * 2:
        raise JupiterSwapRejected("A valid base64 Solana transaction is required.")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise JupiterSwapRejected("A valid base64 Solana transaction is required.") from error
    if len(raw) > MAX_TRANSACTION_BYTES:
        raise JupiterSwapRejected("Solana transaction exceeds the permitted size.")

    signature_count, offset = _shortvec(raw, 0)
    if signature_count < 1 or signature_count > 16:
        raise JupiterSwapRejected("Solana transaction has an invalid signer count.")
    signatures_end = offset + signature_count * 64
    if signatures_end >= len(raw):
        raise JupiterSwapRejected("Jupiter returned an incomplete Solana transaction.")
    signatures = [raw[offset + index * 64:offset + (index + 1) * 64]
                  for index in range(signature_count)]
    message = raw[signatures_end:]
    cursor = 1 if message[0] & 0x80 else 0
    if cursor and (message[0] & 0x7F) != 0:
        raise JupiterSwapRejected("Unsupported Solana transaction version.")
    if len(message) < cursor + 3:
        raise JupiterSwapRejected("Jupiter returned an incomplete Solana message.")
    required_signatures = message[cursor]
    if required_signatures != signature_count:
        raise JupiterSwapRejected("Solana transaction signer metadata did not match.")
    account_count, cursor = _shortvec(message, cursor + 3)
    if account_count < required_signatures or account_count > 128:
        raise JupiterSwapRejected("Solana transaction account metadata is invalid.")
    accounts_end = cursor + account_count * 32
    if accounts_end + 32 > len(message):
        raise JupiterSwapRejected("Jupiter returned incomplete Solana account data.")
    accounts = [message[cursor + index * 32:cursor + (index + 1) * 32]
                for index in range(account_count)]
    return raw, signatures, message, accounts[:required_signatures]


def _expiry(payload: dict[str, Any], current: datetime) -> datetime:
    maximum = current + timedelta(seconds=ORDER_LIFETIME_SECONDS)
    raw_expiry = payload.get("expireAt")
    if not isinstance(raw_expiry, str) or not raw_expiry.strip():
        return maximum
    try:
        provider_expiry = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
        if provider_expiry.tzinfo is None:
            provider_expiry = provider_expiry.replace(tzinfo=timezone.utc)
    except ValueError:
        return maximum
    return min(maximum, provider_expiry.astimezone(timezone.utc))


def _qualified_token(token_address: str, feed: dict[str, Any] | None) -> str:
    token = str(token_address or "").strip()
    if not _valid_solana_address(token):
        raise JupiterSwapRejected("A valid Solana token address is required.")
    public_feed = feed if feed is not None else load_solana_discovery_feed()
    candidates = public_feed.get("candidates") if isinstance(public_feed, dict) else None
    if not any(isinstance(item, dict) and str(item.get("token_address") or "") == token
               for item in candidates or []):
        raise JupiterSwapRejected("Token is not a qualified Solana Discovery candidate.")
    return token


def _prune_orders(current: datetime) -> None:
    stale = [key for key, value in _pending_orders.items()
             if value.expires_at <= current or value.completed]
    for key in stale:
        _pending_orders.pop(key, None)
    if len(_pending_orders) >= MAX_PENDING_ORDERS:
        raise JupiterQuoteUnavailable("The swap pilot is temporarily busy.")


def prepare_jupiter_swap(
    token_address: str,
    amount_sol: Any,
    wallet_address: str,
    *,
    risk_acknowledged: bool = False,
    api_key: str | None = None,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
    now: Callable[[], datetime] = _utcnow,
) -> dict[str, Any]:
    """Request an unsigned Jupiter transaction for one explicitly approved wallet."""
    if risk_acknowledged is not True:
        raise JupiterSwapRejected("Mainnet swap risk must be explicitly acknowledged.")
    output_mint = _qualified_token(token_address, feed)
    wallet = str(wallet_address or "").strip()
    wallet_bytes = _base58_bytes(wallet)
    amount, lamports = _amount_lamports(amount_sol)
    resolved_key = _api_key(api_key)

    try:
        response = request_get(
            JUPITER_ORDER_URL,
            params={"inputMint": WRAPPED_SOL_MINT, "outputMint": output_mint,
                    "amount": str(lamports), "taker": wallet},
            headers={"x-api-key": resolved_key, "accept": "application/json"},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise JupiterQuoteUnavailable("Jupiter swap order is temporarily unavailable.") from error

    if not isinstance(payload, dict) or payload.get("error") or payload.get("errorMessage"):
        raise JupiterQuoteUnavailable("Jupiter could not prepare this swap transaction.")
    if str(payload.get("inputMint") or "") != WRAPPED_SOL_MINT:
        raise JupiterSwapRejected("Jupiter swap input mint did not match SOL.")
    if str(payload.get("outputMint") or "") != output_mint:
        raise JupiterSwapRejected("Jupiter swap output mint did not match the qualified token.")
    if str(payload.get("inAmount") or "") != str(lamports):
        raise JupiterSwapRejected("Jupiter swap input amount did not match the approved amount.")
    if str(payload.get("taker") or "") != wallet:
        raise JupiterSwapRejected("Jupiter swap wallet did not match the connected wallet.")

    request_id = str(payload.get("requestId") or "")
    if REQUEST_ID_PATTERN.fullmatch(request_id) is None:
        raise JupiterSwapRejected("Jupiter did not return a valid swap request identifier.")
    unsigned = payload.get("transaction")
    _, signatures, message, signer_accounts = _transaction_parts(unsigned)
    try:
        wallet_index = signer_accounts.index(wallet_bytes)
    except ValueError as error:
        raise JupiterSwapRejected("Connected wallet is not a signer of the Jupiter transaction.") from error
    if signatures[wallet_index] != bytes(64):
        raise JupiterSwapRejected("Jupiter unexpectedly returned an already-signed wallet transaction.")

    current = now()
    expires_at = _expiry(payload, current)
    if expires_at <= current:
        raise JupiterSwapExpired("The Jupiter swap order has already expired.")
    last_height = payload.get("lastValidBlockHeight")
    last_height_text = str(last_height) if last_height is not None else None
    pending = _PendingOrder(
        token_address=output_mint,
        wallet_address=wallet,
        expires_at=expires_at,
        message_digest=hashlib.sha256(message).digest(),
        wallet_signature_index=wallet_index,
        last_valid_block_height=last_height_text,
    )
    with _pending_lock:
        _prune_orders(current)
        if request_id in _pending_orders:
            raise JupiterSwapRejected("Jupiter returned a duplicate active swap request.")
        _pending_orders[request_id] = pending

    platform_fee = _platform_fee(payload)
    return {
        "status": "WALLET_APPROVAL_REQUIRED",
        "request_id": request_id,
        "unsigned_transaction": unsigned,
        "wallet_address": wallet,
        "input_mint": WRAPPED_SOL_MINT,
        "output_mint": output_mint,
        "input_amount_sol": format(amount.normalize(), "f"),
        "input_amount_lamports": str(lamports),
        "output_amount_raw": str(payload.get("outAmount") or ""),
        "minimum_received_raw": str(payload.get("otherAmountThreshold") or "") or None,
        "router": _label(payload.get("router"), "Jupiter"),
        "price_impact_pct": _number(payload.get("priceImpact"))
                            if payload.get("priceImpact") is not None
                            else _number(payload.get("priceImpactPct")),
        "slippage_bps": int(_number(payload.get("slippageBps")) or 0),
        "jupiter_fee_bps": int(_number(payload.get("feeBps")) or platform_fee["fee_bps"]),
        "dexsato_integrator_fee_bps": 0,
        "expires_at": expires_at.isoformat(),
        "last_valid_block_height": last_height_text,
        "policy": "Only the connected self-custody wallet can approve and sign this transaction.",
    }


def execute_jupiter_swap(
    token_address: str,
    request_id: str,
    wallet_address: str,
    signed_transaction: str,
    *,
    api_key: str | None = None,
    feed: dict[str, Any] | None = None,
    request_post: Callable[..., Any] = requests.post,
    now: Callable[[], datetime] = _utcnow,
) -> dict[str, Any]:
    """Relay one wallet-signed, unchanged Jupiter transaction for settlement."""
    token = _qualified_token(token_address, feed)
    wallet = str(wallet_address or "").strip()
    wallet_bytes = _base58_bytes(wallet)
    order_id = str(request_id or "")
    if REQUEST_ID_PATTERN.fullmatch(order_id) is None:
        raise JupiterSwapRejected("A valid Jupiter swap request identifier is required.")

    raw, signatures, message, signer_accounts = _transaction_parts(signed_transaction)
    signed_digest = hashlib.sha256(raw).digest()
    resolved_key = _api_key(api_key)
    current = now()
    with _pending_lock:
        pending = _pending_orders.get(order_id)
        if pending is None or pending.expires_at <= current or pending.completed:
            raise JupiterSwapExpired("The Jupiter swap order is unavailable or has expired.")
        if pending.token_address != token or pending.wallet_address != wallet:
            raise JupiterSwapRejected("Swap request does not match the approved token and wallet.")
        if not hmac.compare_digest(hashlib.sha256(message).digest(), pending.message_digest):
            raise JupiterSwapRejected("Signed transaction changed the approved Jupiter message.")
        index = pending.wallet_signature_index
        if index >= len(signer_accounts) or signer_accounts[index] != wallet_bytes:
            raise JupiterSwapRejected("Connected wallet is not the approved transaction signer.")
        if index >= len(signatures) or signatures[index] == bytes(64):
            raise JupiterSwapRejected("The connected wallet has not signed this transaction.")
        if pending.signed_digest is not None and not hmac.compare_digest(
            pending.signed_digest, signed_digest
        ):
            raise JupiterSwapRejected("A retry cannot replace the approved signed transaction.")
        if pending.executing:
            raise JupiterSwapRejected("The approved signed transaction is already being submitted.")
        pending.signed_digest = signed_digest
        pending.executing = True

    body: dict[str, str] = {
        "signedTransaction": signed_transaction,
        "requestId": order_id,
    }
    if pending.last_valid_block_height is not None:
        body["lastValidBlockHeight"] = pending.last_valid_block_height

    try:
        response = request_post(
            JUPITER_EXECUTE_URL,
            json=body,
            headers={"x-api-key": resolved_key, "content-type": "application/json",
                     "accept": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        with _pending_lock:
            pending.executing = False
        raise JupiterQuoteUnavailable("Jupiter swap execution is temporarily unavailable.") from error

    if not isinstance(payload, dict) or payload.get("status") not in {"Success", "Failed"}:
        with _pending_lock:
            pending.executing = False
        raise JupiterQuoteUnavailable("Jupiter returned an invalid swap execution response.")
    if payload["status"] == "Success":
        signature = str(payload.get("signature") or "")
        if not signature or len(signature) > 128 or not all(c in BASE58_ALPHABET for c in signature):
            with _pending_lock:
                pending.executing = False
            raise JupiterQuoteUnavailable("Jupiter did not return a valid transaction signature.")
        with _pending_lock:
            pending.executing = False
            pending.completed = True
        return {
            "status": "SWAP_CONFIRMED",
            "request_id": order_id,
            "signature": signature,
            "slot": str(payload.get("slot") or "") or None,
            "input_amount_raw": str(payload.get("inputAmountResult")
                                    or payload.get("totalInputAmount") or "") or None,
            "output_amount_raw": str(payload.get("outputAmountResult")
                                     or payload.get("totalOutputAmount") or "") or None,
            "dexsato_integrator_fee_bps": 0,
        }

    with _pending_lock:
        pending.executing = False
        pending.completed = True
    return {
        "status": "SWAP_FAILED",
        "request_id": order_id,
        "error": str(payload.get("error") or "Jupiter could not settle this transaction.")[:240],
        "code": payload.get("code") if isinstance(payload.get("code"), int) else None,
        "dexsato_integrator_fee_bps": 0,
    }
