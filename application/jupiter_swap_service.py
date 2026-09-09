"""Controlled, non-custodial Jupiter execution for observed discovery tokens.

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
    _amount_token_units,
    _label,
    _number,
    _platform_fee,
    _valid_solana_address,
    _fee_policy,
    _fee_evidence,
    _fee_disclosure,
    _raw_to_ui,
    _token_decimals,
    _trade_direction,
    SOL_DECIMALS,
)
from application.jupiter_fee_policy import FeeEvidence, FeePolicyConfigurationError, require_fee_execution_ready
from application.jupiter_one_shot_swap_gate import (
    GateRejected,bind as bind_one_shot,consume as consume_one_shot,
    record as record_one_shot,require_armed as require_one_shot_armed,
)
from application.solana_discovery_feed_service import load_solana_discovery_record


JUPITER_EXECUTE_URL = "https://api.jup.ag/swap/v2/execute"
ORDER_LIFETIME_SECONDS = 120
MAX_PENDING_ORDERS = 256
MAX_PENDING_ORDERS_PER_WALLET = 4
MAX_TRANSACTION_BYTES = 4096
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
BASE58_DIGITS = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
SYSTEM_PROGRAM = "11111111111111111111111111111111"
COMPUTE_BUDGET_PROGRAM = "ComputeBudget111111111111111111111111111111"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ASSOCIATED_TOKEN_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
JUPITER_V6_PROGRAM = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
DEFAULT_ALLOWED_SWAP_PROGRAMS = frozenset(
    {
        SYSTEM_PROGRAM,
        COMPUTE_BUDGET_PROGRAM,
        TOKEN_PROGRAM,
        TOKEN_2022_PROGRAM,
        ASSOCIATED_TOKEN_PROGRAM,
        JUPITER_V6_PROGRAM,
    }
)


@dataclass(slots=True)
class _PendingOrder:
    token_address: str
    side: str
    input_mint: str
    output_mint: str
    input_amount_raw: str
    wallet_address: str
    expires_at: datetime
    message_digest: bytes
    wallet_signature_index: int
    last_valid_block_height: str | None
    fee_evidence: FeeEvidence
    one_shot_gate_path: str | None = None
    signed_digest: bytes | None = None
    executing: bool = False
    completed: bool = False


@dataclass(frozen=True, slots=True)
class _CompiledInstruction:
    program_index: int
    account_indices: tuple[int, ...]
    data: bytes


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


def _base58_text(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_DIGITS[remainder] + encoded
    zeroes = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * zeroes + (encoded or ("" if zeroes else "1"))


def _allowed_swap_programs() -> frozenset[str]:
    configured = os.getenv("DEXSATO_ALLOWED_SWAP_PROGRAMS", "").strip()
    if not configured:
        return DEFAULT_ALLOWED_SWAP_PROGRAMS
    programs = {item.strip() for item in configured.split(",") if item.strip()}
    if not programs or any(not _valid_solana_address(item) for item in programs):
        raise JupiterQuoteNotConfigured("Allowed Solana swap programs are not configured correctly.")
    return frozenset(programs)


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


def _transaction_parts(
    value: Any,
) -> tuple[bytes, list[bytes], bytes, list[bytes], list[bytes], list[_CompiledInstruction]]:
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
    versioned = bool(message[0] & 0x80)
    cursor = 1 if versioned else 0
    if versioned and (message[0] & 0x7F) != 0:
        raise JupiterSwapRejected("Unsupported Solana transaction version.")
    if len(message) < cursor + 3:
        raise JupiterSwapRejected("Jupiter returned an incomplete Solana message.")
    required_signatures = message[cursor]
    readonly_signed = message[cursor + 1]
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
    cursor = accounts_end + 32
    instruction_count, cursor = _shortvec(message, cursor)
    if instruction_count < 1 or instruction_count > 64:
        raise JupiterSwapRejected("Solana transaction instruction count is invalid.")
    instructions: list[_CompiledInstruction] = []
    for _ in range(instruction_count):
        if cursor >= len(message):
            raise JupiterSwapRejected("Jupiter returned incomplete Solana instructions.")
        program_index = message[cursor]
        account_index_count, cursor = _shortvec(message, cursor + 1)
        accounts_end = cursor + account_index_count
        if accounts_end > len(message):
            raise JupiterSwapRejected("Jupiter returned incomplete Solana instruction accounts.")
        account_indices = tuple(message[cursor:accounts_end])
        data_length, cursor = _shortvec(message, accounts_end)
        data_end = cursor + data_length
        if data_end > len(message):
            raise JupiterSwapRejected("Jupiter returned incomplete Solana instruction data.")
        instructions.append(_CompiledInstruction(program_index, account_indices, message[cursor:data_end]))
        cursor = data_end

    loaded_accounts = 0
    if versioned:
        lookup_count, cursor = _shortvec(message, cursor)
        if lookup_count > 16:
            raise JupiterSwapRejected("Solana transaction has too many address lookups.")
        for _ in range(lookup_count):
            if cursor + 32 > len(message):
                raise JupiterSwapRejected("Jupiter returned incomplete address lookup data.")
            cursor += 32
            writable_count, cursor = _shortvec(message, cursor)
            cursor += writable_count
            readonly_count, cursor = _shortvec(message, cursor)
            cursor += readonly_count
            loaded_accounts += writable_count + readonly_count
            if cursor > len(message):
                raise JupiterSwapRejected("Jupiter returned incomplete address lookup indexes.")
    if cursor != len(message):
        raise JupiterSwapRejected("Jupiter returned trailing Solana transaction data.")

    total_accounts = len(accounts) + loaded_accounts
    if any(
        instruction.program_index >= total_accounts
        or any(index >= total_accounts for index in instruction.account_indices)
        for instruction in instructions
    ):
        raise JupiterSwapRejected("Solana transaction instruction account index is invalid.")
    if readonly_signed != 0:
        raise JupiterSwapRejected("Transaction payer must be a writable signer.")
    return raw, signatures, message, accounts[:required_signatures], accounts, instructions


def _validate_transaction_policy(
    signer_accounts: list[bytes],
    static_accounts: list[bytes],
    instructions: list[_CompiledInstruction],
    wallet_bytes: bytes,
    input_lamports: int,
) -> int:
    """Validate signer, payer, program and bounded SOL-transfer policy."""
    if signer_accounts != [wallet_bytes] or not static_accounts or static_accounts[0] != wallet_bytes:
        raise JupiterSwapRejected("Connected wallet must be the sole transaction signer and payer.")

    allowed = _allowed_swap_programs()
    jupiter_seen = False
    system_transferred = 0
    for instruction in instructions:
        if instruction.program_index >= len(static_accounts):
            raise JupiterSwapRejected("Solana instruction program must use a verified static account.")
        program = _base58_text(static_accounts[instruction.program_index])
        if program not in allowed:
            raise JupiterSwapRejected("Jupiter transaction uses a program that is not allowed.")
        if program == JUPITER_V6_PROGRAM:
            jupiter_seen = True
            if 0 not in instruction.account_indices:
                raise JupiterSwapRejected("Jupiter instruction is not authorized by the connected wallet.")
        elif program == SYSTEM_PROGRAM:
            if len(instruction.data) != 12 or int.from_bytes(instruction.data[:4], "little") != 2:
                raise JupiterSwapRejected("Unsupported System Program instruction in Jupiter transaction.")
            if not instruction.account_indices or instruction.account_indices[0] != 0:
                raise JupiterSwapRejected("System transfer is not sourced from the connected wallet.")
            transferred = int.from_bytes(instruction.data[4:], "little")
            system_transferred += transferred
            if transferred < 1 or system_transferred > input_lamports:
                raise JupiterSwapRejected("System transfer exceeds the approved SOL amount.")
        elif program in {TOKEN_PROGRAM, TOKEN_2022_PROGRAM}:
            if not instruction.data or instruction.data[0] not in {9, 17}:
                raise JupiterSwapRejected("Unsupported token-program instruction in Jupiter transaction.")
            if instruction.data[0] == 9 and 0 not in instruction.account_indices:
                raise JupiterSwapRejected("Token close instruction is not authorized by the connected wallet.")
        elif program == ASSOCIATED_TOKEN_PROGRAM:
            if instruction.data not in {b"", b"\x00", b"\x01"}:
                raise JupiterSwapRejected("Unsupported associated-token instruction in Jupiter transaction.")
            if not instruction.account_indices or instruction.account_indices[0] != 0:
                raise JupiterSwapRejected("Associated-token creation is not paid by the connected wallet.")

    if not jupiter_seen:
        raise JupiterSwapRejected("Jupiter transaction does not invoke the approved Jupiter program.")
    return 0


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


def _observed_token(token_address: str, feed: dict[str, Any] | None) -> str:
    token = str(token_address or "").strip()
    if not _valid_solana_address(token):
        raise JupiterSwapRejected("A valid Solana token address is required.")
    if feed is None:
        observed = load_solana_discovery_record(token)
    else:
        candidates = feed.get("candidates") if isinstance(feed, dict) else None
        observed = next(
            (
                item for item in candidates or []
                if isinstance(item, dict) and str(item.get("token_address") or "") == token
            ),
            None,
        )
    if observed is None:
        raise JupiterSwapRejected("Token is not an observed Solana Discovery token.")
    return token


def _prune_orders(current: datetime, wallet_address: str) -> None:
    stale = [key for key, value in _pending_orders.items()
             if value.expires_at <= current or value.completed]
    for key in stale:
        _pending_orders.pop(key, None)
    if len(_pending_orders) >= MAX_PENDING_ORDERS:
        raise JupiterQuoteUnavailable("The swap pilot is temporarily busy.")
    wallet_orders = sum(
        1
        for value in _pending_orders.values()
        if value.wallet_address == wallet_address
    )
    if wallet_orders >= MAX_PENDING_ORDERS_PER_WALLET:
        raise JupiterQuoteUnavailable(
            "This wallet has too many pending swap reviews. Complete or wait for an existing review to expire."
        )


def _order_error_message(payload: dict[str, Any], side: str) -> str | None:
    """Map known Jupiter order failures to safe, actionable D6.1 UX messages."""
    raw = str(payload.get("errorMessage") or payload.get("error") or "").strip()
    if not raw:
        return None
    normalized = raw.casefold()
    if "insufficient funds" in normalized or "insufficient balance" in normalized:
        if side == "sell":
            return "Insufficient token balance. Reduce the sell amount or check the connected wallet."
        return "Insufficient SOL balance. Reduce the swap amount or add SOL to your connected wallet."
    return "Jupiter could not prepare this swap transaction."


def prepare_jupiter_swap(
    token_address: str,
    amount_sol: Any,
    wallet_address: str,
    *,
    side: str = "buy",
    risk_acknowledged: bool = False,
    api_key: str | None = None,
    feed: dict[str, Any] | None = None,
    request_get: Callable[..., Any] = requests.get,
    request_post: Callable[..., Any] = requests.post,
    rpc_url: str | None = None,
    now: Callable[[], datetime] = _utcnow,
) -> dict[str, Any]:
    """Request an unsigned Jupiter transaction for one explicitly approved wallet."""
    if risk_acknowledged is not True:
        raise JupiterSwapRejected("Mainnet swap risk must be explicitly acknowledged.")
    token_mint = _observed_token(token_address, feed)
    direction = _trade_direction(side)
    wallet = str(wallet_address or "").strip()
    wallet_bytes = _base58_bytes(wallet)
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
            raise JupiterQuoteUnavailable("Token decimals are unavailable for a sell order.")
        amount, input_raw = _amount_token_units(amount_sol, input_decimals)
        input_mint = token_mint
        output_mint = WRAPPED_SOL_MINT
    resolved_key = _api_key(api_key)

    fee_policy = _fee_policy()
    gate_path=None;gate=None
    try:
        one_shot_mode=os.getenv("DEXSATO_JUPITER_ONE_SHOT_MODE","false").strip().lower()
        if one_shot_mode not in {"true","false"}:
            raise GateRejected("INVALID_ONE_SHOT_MODE")
        if fee_policy.enabled and one_shot_mode=="true":
            gate_path=os.getenv("DEXSATO_JUPITER_ONE_SHOT_GATE_PATH","").strip()
            if not gate_path:raise GateRejected("ONE_SHOT_GATE_PATH_REQUIRED")
            gate=require_one_shot_armed(gate_path,output_mint,wallet,input_raw,fee_policy,now())
        else:require_fee_execution_ready(fee_policy)
    except (FeePolicyConfigurationError,GateRejected) as error:
        raise JupiterQuoteNotConfigured("Fee-enabled swap execution is not activated for this exact one-shot order.") from error

    with _pending_lock:
        _prune_orders(now(), wallet)

    try:
        response = request_get(
            JUPITER_ORDER_URL,
            params={"inputMint": input_mint, "outputMint": output_mint,
                    "amount": str(input_raw), "taker": wallet,
                "excludeRouters": "jupiterz,dflow,okx",
                    **fee_policy.request_parameters()},
            headers={"x-api-key": resolved_key, "accept": "application/json"},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise JupiterQuoteUnavailable("Jupiter swap order is temporarily unavailable.") from error

    if not isinstance(payload, dict):
        raise JupiterQuoteUnavailable("Jupiter could not prepare this swap transaction.")
    provider_error = _order_error_message(payload, direction)
    if provider_error is not None:
        raise JupiterQuoteUnavailable(provider_error)
    fee_evidence = _fee_evidence(fee_policy, payload, input_mint, output_mint)
    fee_disclosure = _fee_disclosure(
        fee_evidence, payload, input_raw, input_mint, output_mint,
    )
    if str(payload.get("inputMint") or "") != input_mint:
        raise JupiterSwapRejected("Jupiter swap input mint did not match the approved trade side.")
    if str(payload.get("outputMint") or "") != output_mint:
        raise JupiterSwapRejected("Jupiter swap output mint did not match the qualified token.")
    if str(payload.get("inAmount") or "") != str(input_raw):
        raise JupiterSwapRejected("Jupiter swap input amount did not match the approved amount.")
    if str(payload.get("taker") or "") != wallet:
        raise JupiterSwapRejected("Jupiter swap wallet did not match the connected wallet.")

    request_id = str(payload.get("requestId") or "")
    if REQUEST_ID_PATTERN.fullmatch(request_id) is None:
        raise JupiterSwapRejected("Jupiter did not return a valid swap request identifier.")
    unsigned = payload.get("transaction")
    _, signatures, message, signer_accounts, static_accounts, instructions = _transaction_parts(unsigned)
    wallet_index = _validate_transaction_policy(
        signer_accounts,
        static_accounts,
        instructions,
        wallet_bytes,
        input_raw if direction == "buy" else 0,
    )
    if signatures[wallet_index] != bytes(64):
        raise JupiterSwapRejected("Jupiter unexpectedly returned an already-signed wallet transaction.")

    current = now()
    expires_at = _expiry(payload, current)
    if expires_at <= current:
        raise JupiterSwapExpired("The Jupiter swap order has already expired.")
    last_height = payload.get("lastValidBlockHeight")
    last_height_text = str(last_height) if last_height is not None else None
    pending = _PendingOrder(
        token_address=token_mint,
        side=direction,
        input_mint=input_mint,
        output_mint=output_mint,
        input_amount_raw=str(input_raw),
        wallet_address=wallet,
        expires_at=expires_at,
        message_digest=hashlib.sha256(message).digest(),
        wallet_signature_index=wallet_index,
        last_valid_block_height=last_height_text,
        fee_evidence=fee_evidence,
        one_shot_gate_path=gate_path,
    )
    if gate is not None:
        try:bind_one_shot(gate_path,gate,request_id,message,
                          str(payload.get("otherAmountThreshold") or ""))
        except GateRejected as error:
            raise JupiterSwapRejected("The one-shot approval changed before order binding.") from error
    with _pending_lock:
        _prune_orders(current, wallet)
        if request_id in _pending_orders:
            raise JupiterSwapRejected("Jupiter returned a duplicate active swap request.")
        _pending_orders[request_id] = pending

    platform_fee = _platform_fee(payload)
    if output_mint == WRAPPED_SOL_MINT:
        output_decimals, output_decimals_source = SOL_DECIMALS, "Solana protocol"
    else:
        try:
            output_decimals = int(payload.get("outputDecimals"))
            if not 0 <= output_decimals <= 18:
                raise ValueError
            output_decimals_source = "Jupiter"
        except (TypeError, ValueError):
            output_decimals, output_decimals_source = None, None
    output_raw = str(payload.get("outAmount") or "")
    minimum_raw = str(payload.get("otherAmountThreshold") or "") or None
    return {
        "status": "WALLET_APPROVAL_REQUIRED",
        "request_id": request_id,
        "unsigned_transaction": unsigned,
        "wallet_address": wallet,
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
        "output_amount_raw": output_raw,
        "output_amount_ui": _raw_to_ui(output_raw, output_decimals),
        "output_decimals": output_decimals,
        "output_decimals_source": output_decimals_source,
        "minimum_received_raw": minimum_raw,
        "minimum_received_ui": _raw_to_ui(minimum_raw, output_decimals),
        "router": _label(payload.get("router"), "Jupiter"),
        "price_impact_pct": _number(payload.get("priceImpact"))
                            if payload.get("priceImpact") is not None
                            else _number(payload.get("priceImpactPct")),
        "slippage_bps": int(_number(payload.get("slippageBps")) or 0),
        "jupiter_fee_bps": int(_number(payload.get("feeBps")) or platform_fee["fee_bps"]),
        **fee_evidence.public_fields(),
        "fee_disclosure": fee_disclosure,
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
    token = _observed_token(token_address, feed)
    wallet = str(wallet_address or "").strip()
    wallet_bytes = _base58_bytes(wallet)
    order_id = str(request_id or "")
    if REQUEST_ID_PATTERN.fullmatch(order_id) is None:
        raise JupiterSwapRejected("A valid Jupiter swap request identifier is required.")

    raw, signatures, message, signer_accounts, _, _ = _transaction_parts(signed_transaction)
    signed_digest = hashlib.sha256(raw).digest()
    resolved_key = _api_key(api_key)
    current = now()
    with _pending_lock:
        pending = _pending_orders.get(order_id)
        if pending is None or pending.expires_at <= current or pending.completed:
            raise JupiterSwapExpired("The Jupiter swap order is unavailable or has expired.")
        if pending.token_address != token or pending.wallet_address != wallet:
            raise JupiterSwapRejected("Swap request does not match the approved token and wallet.")
        if pending.fee_evidence.policy != _fee_policy():
            raise JupiterSwapRejected("Swap request fee policy changed. Request a new quote and order.")
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

    if pending.one_shot_gate_path:
        try:consume_one_shot(pending.one_shot_gate_path,order_id,message,signed_digest.hex())
        except GateRejected as error:
            with _pending_lock:pending.executing=False
            raise JupiterSwapRejected("The one-shot approval is unavailable or does not match this transaction.") from error

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
        if pending.one_shot_gate_path:record_one_shot(pending.one_shot_gate_path,"Success",signature)
        return {
            "status": "SWAP_CONFIRMED",
            "request_id": order_id,
            "side": pending.side,
            "input_mint": pending.input_mint,
            "output_mint": pending.output_mint,
            "signature": signature,
            "slot": str(payload.get("slot") or "") or None,
            "input_amount_raw": str(payload.get("inputAmountResult")
                                    or payload.get("totalInputAmount") or "") or None,
            "output_amount_raw": str(payload.get("outputAmountResult")
                                     or payload.get("totalOutputAmount") or "") or None,
            **pending.fee_evidence.execution_fields(),
        }

    with _pending_lock:
        pending.executing = False
        pending.completed = True
    if pending.one_shot_gate_path:
        record_one_shot(pending.one_shot_gate_path,"Failed",
                        error=payload.get("error"),code=payload.get("code"))
    return {
        "status": "SWAP_FAILED",
        "request_id": order_id,
        "side": pending.side,
        "error": str(payload.get("error") or "Jupiter could not settle this transaction.")[:240],
        "code": payload.get("code") if isinstance(payload.get("code"), int) else None,
        **pending.fee_evidence.execution_fields(),
    }
