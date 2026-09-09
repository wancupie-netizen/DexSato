"""Honest fee disclosure: estimates are not transaction debits or receipts."""
from decimal import Decimal
import os

from application.jupiter_referral_verification import verify_referral_accounts
from application.jupiter_fee_policy import FeePolicyRejected, WSOL_MINT


def build_fee_disclosure(
    evidence, payload, input_raw, output_mint=None, *, input_mint=WSOL_MINT,
):
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
    if str(raw) != str(input_raw) or type(raw) not in (str, int) or payload.get("gasless") is True:
        raise FeePolicyRejected("Fee estimate input or gasless contract requires review.")
    observation = verify_referral_accounts(policy.referral_account,
        os.getenv("DEXSATO_JUPITER_REFERRAL_PARTNER", "").strip(), mints=(WSOL_MINT,))
    platform_fee = payload.get("platformFee")
    platform_raw = platform_fee.get("amount") if isinstance(platform_fee, dict) else None
    if evidence.fee_mint == WSOL_MINT and input_mint == WSOL_MINT:
        fee_raw = Decimal(input_raw) * Decimal(policy.fee_bps) / Decimal(10000)
    elif evidence.fee_mint == WSOL_MINT and str(platform_raw or "").isdigit():
        fee_raw = Decimal(str(platform_raw))
    else:
        raise FeePolicyRejected("Fee estimate mint or amount requires review.")
    estimate = fee_raw / Decimal(10**9)
    live_flag = os.getenv(
        "DEXSATO_JUPITER_LIVE_FEE_EXECUTION_ENABLED", "false"
    ).strip().lower()
    if live_flag not in {"true", "false"}:
        raise FeePolicyRejected("Live referral execution configuration is invalid.")

    one_shot_flag = os.getenv("DEXSATO_JUPITER_ONE_SHOT_MODE", "false").strip().lower()
    if one_shot_flag not in {"true", "false"}:
        raise FeePolicyRejected("One-shot referral execution configuration is invalid.")
    if live_flag == "true" and one_shot_flag == "true":
        raise FeePolicyRejected("Live and one-shot referral execution cannot run together.")

    live_ready = live_flag == "true"
    one_shot_ready = False
    if not live_ready and one_shot_flag == "true":
        try:
            from application.jupiter_one_shot_swap_gate import (
                INPUT_LAMPORTS, TAP_MINT, WALLET, require_armed,
            )
            path = os.getenv("DEXSATO_JUPITER_ONE_SHOT_GATE_PATH", "").strip()
            gate = require_armed(path, TAP_MINT, WALLET, input_raw, policy)
            one_shot_ready = (gate.get("output_mint") == TAP_MINT
                              and output_mint == TAP_MINT
                              and input_mint == WSOL_MINT
                              and input_raw == INPUT_LAMPORTS)
        except Exception:
            one_shot_ready = False

    execution_ready = live_ready or one_shot_ready
    activation_scope = (
        "LIVE_REFERRAL" if live_ready
        else "ONE_SHOT_TAP" if one_shot_ready
        else "PREVIEW_ONLY"
    )
    activation_note = (
        "DexSato live referral execution is active."
        if live_ready
        else "One-shot TAP execution gate is armed."
        if one_shot_ready
        else "Fee execution is not activated."
    )
    return {**base, "execution_ready": execution_ready,
            "activation_scope": activation_scope,
            "integrator_fee_amount_ui": format(estimate, "f"),
            "integrator_fee_symbol": "WSOL", "referral_verification": "RPC_ACCOUNT_VERIFIED",
            "referral_checked_at": observation.checked_at, "referral_slot": observation.slot,
            "jupiter_share_percent": format(Decimal(10000 - observation.partner_share_bps) / 100, ".2f"),
            "note": "Estimated integrator fee includes Jupiter's share; not an additional charge. "
                    "Final debit and output depend on the transaction. " + activation_note}
