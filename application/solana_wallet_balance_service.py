"""Read-only Solana wallet balances used by the percentage trade controls."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN
import os
from typing import Any, Callable

import requests

from application.solana_discovery_feed_service import load_solana_discovery_record


SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
BASE58_ALPHABET = frozenset("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
SOL_DECIMALS = 9
MIN_SOL_AMOUNT = Decimal("0.001")
MAX_SOL_AMOUNT = Decimal("100")
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
KNOWN_TOKEN_PROGRAMS = frozenset({TOKEN_PROGRAM, TOKEN_2022_PROGRAM})
SOL_FEE_RESERVE_LAMPORTS = 5_000_000
MAX_BUY_LAMPORTS = int(MAX_SOL_AMOUNT * (Decimal(10) ** SOL_DECIMALS))
MAX_INPUT_RAW = 18_446_744_073_709_551_615


class SolanaWalletBalanceUnavailable(RuntimeError):
    """Raised when the authoritative RPC balance cannot be read safely."""


class SolanaWalletBalanceRejected(ValueError):
    """Raised when a wallet, token, or requested amount fails validation."""


def _valid_solana_address(value: str) -> bool:
    return 32 <= len(value) <= 44 and all(character in BASE58_ALPHABET for character in value)


def _decimal_amount(value: Any, label: str) -> Decimal:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise SolanaWalletBalanceRejected(f"{label} amount must be a valid number.") from error
    if not amount.is_finite() or amount <= 0:
        raise SolanaWalletBalanceRejected(f"{label} amount must be greater than zero.")
    return amount


def _amount_lamports(value: Any) -> tuple[Decimal, int]:
    amount = _decimal_amount(value, "SOL")
    if amount < MIN_SOL_AMOUNT or amount > MAX_SOL_AMOUNT:
        raise SolanaWalletBalanceRejected("SOL amount must be between 0.001 and 100.")
    return amount, int((amount * (10 ** SOL_DECIMALS)).to_integral_value(rounding=ROUND_DOWN))


def _amount_token_units(value: Any, decimals: int) -> tuple[Decimal, int]:
    amount = _decimal_amount(value, "Token")
    raw = int((amount * (10 ** decimals)).to_integral_value(rounding=ROUND_DOWN))
    if raw <= 0:
        raise SolanaWalletBalanceRejected("Token amount is too small.")
    if raw > MAX_INPUT_RAW:
        raise SolanaWalletBalanceRejected("Token amount exceeds the supported swap limit.")
    return amount, raw


def _rpc_balances(
    token: str,
    wallet: str,
    *,
    request_post: Callable[..., Any],
    rpc_url: str | None,
) -> tuple[int, Any, int | None]:
    endpoint = (rpc_url or os.getenv("SOLANA_RPC_URL", "") or SOLANA_RPC_URL).strip()
    try:
        response = request_post(
            endpoint,
            json=[
                {
                    "jsonrpc": "2.0", "id": "sol", "method": "getBalance",
                    "params": [wallet, {"commitment": "confirmed"}],
                },
                {
                    "jsonrpc": "2.0", "id": "token", "method": "getTokenAccountsByOwner",
                    "params": [
                        wallet, {"mint": token},
                        {"encoding": "jsonParsed", "commitment": "confirmed"},
                    ],
                },
            ],
            headers={"accept": "application/json", "content-type": "application/json"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise SolanaWalletBalanceUnavailable(
            "Solana wallet balance is temporarily unavailable."
        ) from error
    if not isinstance(payload, list):
        raise SolanaWalletBalanceUnavailable("Solana RPC did not return a usable wallet balance.")
    responses = {
        item.get("id"): item
        for item in payload
        if isinstance(item, dict) and item.get("id") in {"sol", "token"}
    }
    if set(responses) != {"sol", "token"}:
        raise SolanaWalletBalanceUnavailable("Solana RPC returned an incomplete wallet balance.")
    results: dict[str, dict[str, Any]] = {}
    slots: list[int] = []
    for key in ("sol", "token"):
        item = responses[key]
        result = item.get("result")
        if item.get("error") or not isinstance(result, dict):
            raise SolanaWalletBalanceUnavailable("Solana RPC did not return a usable wallet balance.")
        results[key] = result
        context = result.get("context") if isinstance(result.get("context"), dict) else {}
        slot = context.get("slot")
        if isinstance(slot, int) and slot >= 0:
            slots.append(slot)
    sol_value = results["sol"].get("value")
    if not isinstance(sol_value, int) or sol_value < 0:
        raise SolanaWalletBalanceUnavailable("Solana RPC returned an invalid SOL balance.")
    return sol_value, results["token"].get("value"), max(slots) if slots else None


def _raw_ui(raw: int, decimals: int) -> str:
    digits = str(max(0, raw)).rjust(decimals + 1, "0")
    if decimals == 0:
        return digits
    whole, fraction = digits[:-decimals], digits[-decimals:].rstrip("0")
    return whole if not fraction else f"{whole}.{fraction}"


def _token_accounts(value: Any, token: str, wallet: str) -> tuple[list[int], int | None]:
    if not isinstance(value, list):
        raise SolanaWalletBalanceUnavailable("Solana RPC returned invalid token-account data.")
    balances: list[int] = []
    decimals_seen: set[int] = set()
    for entry in value:
        account = entry.get("account") if isinstance(entry, dict) else None
        if not isinstance(account, dict) or account.get("owner") not in KNOWN_TOKEN_PROGRAMS:
            continue
        data = account.get("data")
        parsed = data.get("parsed") if isinstance(data, dict) else None
        info = parsed.get("info") if isinstance(parsed, dict) else None
        token_amount = info.get("tokenAmount") if isinstance(info, dict) else None
        if (
            not isinstance(info, dict)
            or info.get("mint") != token
            or info.get("owner") != wallet
            or not isinstance(token_amount, dict)
        ):
            continue
        raw = token_amount.get("amount")
        decimals = token_amount.get("decimals")
        if not isinstance(raw, str) or not raw.isdigit() or not isinstance(decimals, int) or not 0 <= decimals <= 18:
            raise SolanaWalletBalanceUnavailable("Solana RPC returned invalid token balance metadata.")
        balances.append(int(raw))
        decimals_seen.add(decimals)
    if len(decimals_seen) > 1:
        raise SolanaWalletBalanceUnavailable("Token accounts returned inconsistent decimal metadata.")
    return balances, next(iter(decimals_seen), None)


def load_solana_wallet_balance(
    token_address: str,
    wallet_address: str,
    *,
    request_post: Callable[..., Any] = requests.post,
    rpc_url: str | None = None,
    record_loader: Callable[[str], Any] = load_solana_discovery_record,
) -> dict[str, Any]:
    """Return raw, authoritative balances without requesting wallet permissions."""
    token = str(token_address or "").strip()
    wallet = str(wallet_address or "").strip()
    if not _valid_solana_address(token):
        raise SolanaWalletBalanceRejected("A valid Solana token address is required.")
    if not _valid_solana_address(wallet):
        raise SolanaWalletBalanceRejected("A valid connected Solana wallet is required.")
    if record_loader(token) is None:
        raise SolanaWalletBalanceRejected("Token is not an observed Solana Discovery token.")

    sol_value, token_value, slot = _rpc_balances(
        token, wallet, request_post=request_post, rpc_url=rpc_url,
    )
    balances, token_decimals = _token_accounts(token_value, token, wallet)
    nonzero = [balance for balance in balances if balance > 0]
    token_total = sum(balances)
    percentage_ready = len(nonzero) <= 1 and token_decimals is not None
    token_available = token_total if percentage_ready else None
    spendable = min(max(0, sol_value - SOL_FEE_RESERVE_LAMPORTS), MAX_BUY_LAMPORTS)
    return {
        "status": "BALANCE_READY",
        "wallet_address": wallet,
        "token_mint": token,
        "sol_balance_lamports": str(sol_value),
        "sol_balance_ui": _raw_ui(sol_value, SOL_DECIMALS),
        "buy_spendable_lamports": str(spendable),
        "buy_spendable_ui": _raw_ui(spendable, SOL_DECIMALS),
        "sol_fee_reserve_lamports": str(SOL_FEE_RESERVE_LAMPORTS),
        "sol_fee_reserve_ui": _raw_ui(SOL_FEE_RESERVE_LAMPORTS, SOL_DECIMALS),
        "token_balance_raw": str(token_available) if token_available is not None else None,
        "token_total_balance_raw": str(token_total),
        "token_balance_ui": (
            _raw_ui(token_available, token_decimals)
            if token_available is not None and token_decimals is not None else None
        ),
        "token_decimals": token_decimals,
        "token_account_count": len(balances),
        "sell_percentage_ready": percentage_ready,
        "slot": slot,
    }


def validate_wallet_trade_amount(balance: dict[str, Any], side: str, amount: Any) -> None:
    """Fail closed if a requested trade exceeds the latest authoritative balance."""
    direction = str(side or "buy").strip().lower()
    if direction == "buy":
        _, raw = _amount_lamports(amount)
        try:
            available = int(str(balance.get("buy_spendable_lamports") or "-1"))
        except (TypeError, ValueError) as error:
            raise SolanaWalletBalanceUnavailable("Wallet balance metadata is invalid.") from error
        if raw > available:
            raise SolanaWalletBalanceRejected(
                "Insufficient spendable SOL balance. Reduce the amount or add SOL for fees."
            )
        return
    if direction == "sell":
        decimals = balance.get("token_decimals")
        if not isinstance(decimals, int):
            raise SolanaWalletBalanceUnavailable("Token balance decimals are unavailable.")
        _, raw = _amount_token_units(amount, decimals)
        try:
            available = int(str(balance.get("token_total_balance_raw") or "-1"))
        except (TypeError, ValueError) as error:
            raise SolanaWalletBalanceUnavailable("Wallet balance metadata is invalid.") from error
        if raw > available:
            raise SolanaWalletBalanceRejected(
                "Insufficient token balance. Reduce the sell amount."
            )
        return
    raise SolanaWalletBalanceRejected("Trade side must be buy or sell.")
