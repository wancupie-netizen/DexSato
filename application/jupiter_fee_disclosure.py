"""Honest fee disclosure: estimates are not transaction debits or receipts."""
from decimal import Decimal
import os

from application.jupiter_referral_verification import verify_referral_accounts
from application.jupiter_fee_policy import FeePolicyRejected, WSOL_MINT


def build_fee_disclosure(evidence, payload, input_lamports):
    policy = evidence.policy
    base = {"version": 1, "policy_id": policy.fingerprint,
            "integrator_fee_bps": policy.fee_bps,
            "integrator_fee_percent": format(Decimal(policy.fee_bps) / 100, ".2f"),
            "amount_kind": "ESTIMATE" if policy.enabled else "ZERO",
            "fee_receipt_verified": False, "execution_ready": not policy.enabled,
            "network_fee_note": "Network fees and account rent are separate; review your wallet."}
    if not policy.enabled:
        return {**base, "integrator_fee_amount_ui": "0", "integrator_fee_symbol": "SOL",
                "referral_verification": "NOT_REQUIRED",
                "note": "DexSato fee is zero. Jupiter route fees may still apply."}
    # Bind the estimate to exactly the server-approved input, never a client fee.
    raw = payload.get("inAmount")
    if str(raw) != str(input_lamports) or type(raw) not in (str, int) or payload.get("gasless") is True:
        raise FeePolicyRejected("Fee estimate input or gasless contract requires review.")
    observation = verify_referral_accounts(policy.referral_account,
        os.getenv("DEXSATO_JUPITER_REFERRAL_PARTNER", "").strip(), mints=(WSOL_MINT,))
    estimate = Decimal(input_lamports) * Decimal(policy.fee_bps) / Decimal(10000 * 10**9)
    return {**base, "integrator_fee_amount_ui": format(estimate, "f"),
            "integrator_fee_symbol": "WSOL", "referral_verification": "RPC_ACCOUNT_VERIFIED",
            "referral_checked_at": observation.checked_at, "referral_slot": observation.slot,
            "jupiter_share_percent": format(Decimal(10000 - observation.partner_share_bps) / 100, ".2f"),
            "note": "Estimated integrator fee includes Jupiter's share; not an additional charge. "
                    "Final debit and output depend on the transaction. Fee execution is not activated."}
