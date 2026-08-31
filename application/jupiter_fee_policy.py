"""Server-only Swap V2 referral policy. No keys, RPC writes or custody.

PROVIDER_VALIDATED means response validation only, not proof of on-chain
account ownership or fee receipt. Activation requires the later UI/on-chain gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import os
from typing import Any, Mapping


WSOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SUPPORTED_FEE_MINTS = frozenset({WSOL_MINT, USDC_MINT})
_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


class FeePolicyConfigurationError(RuntimeError):
    """Invalid server configuration; never include its value in the error."""


class FeePolicyRejected(RuntimeError):
    """Provider response does not satisfy the server's referral policy."""


def valid_public_key(value: Any) -> bool:
    if not isinstance(value, str) or not 32 <= len(value) <= 44:
        return False
    number = 0
    for character in value:
        if character not in _BASE58:
            return False
        number = number * 58 + _BASE58.index(character)
    size = (number.bit_length() + 7) // 8 + len(value) - len(value.lstrip("1"))
    return size == 32 and number != 0


def _integer(value: Any) -> int | None:
    if type(value) is int:
        return value
    if isinstance(value, str) and 1 <= len(value) <= 5 and value.isascii() and value.isdigit():
        return int(value)
    return None


@dataclass(frozen=True, slots=True)
class FeePolicy:
    enabled: bool = False
    referral_account: str | None = None
    fee_bps: int = 0

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(
            [self.enabled, self.referral_account, self.fee_bps],
            separators=(",", ":"),
        ).encode("ascii")).hexdigest()

    def request_parameters(self) -> dict[str, str]:
        if not self.enabled:
            return {}
        return {"referralAccount": self.referral_account, "referralFee": str(self.fee_bps)}


@dataclass(frozen=True, slots=True)
class FeeEvidence:
    policy: FeePolicy
    fee_mint: str | None = None

    def execution_fields(self) -> dict[str, Any]:
        # Preserve the historical zero-fee execution response while disabled.
        return self.public_fields() if self.policy.enabled else {"dexsato_integrator_fee_bps": 0}

    def public_fields(self) -> dict[str, Any]:
        return {
            "dexsato_integrator_fee_bps": self.policy.fee_bps,
            "dexsato_integrator_fee_status": (
                "PROVIDER_VALIDATED" if self.policy.enabled else "NOT_CONFIGURED"
            ),
            "dexsato_referral_account": self.policy.referral_account,
            "dexsato_fee_mint": self.fee_mint,
            # platformFee.amount is NOT an authoritative DexSato fee amount.
            "dexsato_fee_amount_raw": None,
            "dexsato_fee_policy_id": self.policy.fingerprint,
        }


def read_fee_policy(environment: Mapping[str, str] | None = None) -> FeePolicy:
    env = os.environ if environment is None else environment
    flag = env.get("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower()
    if flag not in {"true", "false"}:
        raise FeePolicyConfigurationError("DEXSATO_JUPITER_FEE_ENABLED must be true or false.")
    if flag == "false":
        return FeePolicy()
    account = env.get("DEXSATO_JUPITER_REFERRAL_ACCOUNT", "").strip()
    if not valid_public_key(account) or account in SUPPORTED_FEE_MINTS:
        raise FeePolicyConfigurationError("DEXSATO_JUPITER_REFERRAL_ACCOUNT must be a valid public account.")
    bps = _integer(env.get("DEXSATO_JUPITER_REFERRAL_FEE_BPS", "").strip())
    if bps is None or not 50 <= bps <= 255:
        raise FeePolicyConfigurationError("DEXSATO_JUPITER_REFERRAL_FEE_BPS must be an integer from 50 to 255.")
    return FeePolicy(True, account, bps)


@lru_cache(maxsize=1)
def get_fee_policy() -> FeePolicy:
    """Freeze configuration for this process. Changes require a server restart."""
    return read_fee_policy()


def require_fee_execution_ready(policy: FeePolicy) -> None:
    """Phase 03-C safety gate; NOT an environment-toggle bypass.

Phase 03-D adds account verification and disclosure, but does not activate fees.
Remove this gate only after owner approval, a verified live account report and
reviewed transaction-level fee destination/amount checks for controlled testing.
Matching provider echoes alone cannot prove referral-token-account ownership
or distinguish every default-fee fallback (including a coincidental 50 bps).
"""
    if policy.enabled:
        raise FeePolicyConfigurationError(
            "Fee-enabled execution awaits reviewed activation and transaction fee validation."
        )


def validate_fee_response(
    policy: FeePolicy, payload: dict[str, Any], *, input_mint: str, output_mint: str,
) -> FeeEvidence:
    referral = payload.get("referralAccount")
    if not policy.enabled:
        if referral not in (None, ""):
            raise FeePolicyRejected("Unexpected referral account on a fee-disabled order.")
        return FeeEvidence(policy)
    if referral != policy.referral_account:
        raise FeePolicyRejected("Jupiter referral account did not match the server policy.")
    if _integer(payload.get("feeBps")) != policy.fee_bps:
        raise FeePolicyRejected("Jupiter fee rate did not match the server policy.")
    mint = payload.get("feeMint")
    if not isinstance(mint, str) or mint not in SUPPORTED_FEE_MINTS or mint not in {input_mint, output_mint}:
        raise FeePolicyRejected("Jupiter fee mint is missing or unsupported by the server policy.")
    # SOL has the highest fee-mint priority for the current SOL-input flow.
    if input_mint == WSOL_MINT and mint != WSOL_MINT:
        raise FeePolicyRejected("Jupiter fee mint did not match the SOL-input policy.")
    return FeeEvidence(policy, mint)
