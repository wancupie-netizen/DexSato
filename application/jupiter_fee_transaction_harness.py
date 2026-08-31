"""Offline operator diagnostics, NOT an execution authorization service.

Never signs, submits, fetches RPC, or changes fee settings. Imported production
parsers are exercised against unsigned evidence. A structural pass NEVER proves
Jupiter instruction semantics, fee amount/destination, or fee receipt.
"""
from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path

from application.jupiter_fee_policy import (
    WSOL_MINT, FeePolicy, FeePolicyRejected, read_fee_policy,
    valid_public_key, validate_fee_response,
)
from application.jupiter_referral_verification import referral_token_address
from application.jupiter_swap_service import (
    _transaction_parts, _validate_transaction_policy, _base58_bytes,
    _base58_text, DEFAULT_ALLOWED_SWAP_PROGRAMS, JupiterSwapRejected,
)

MAX_EVIDENCE_BYTES = 65536


class HarnessRejected(ValueError):
    """Fixed reason code only; no transaction or upstream exception disclosure."""


def reject(code):
    raise HarnessRejected(code)


def amount(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 20 or not value.isascii() or not value.isdigit():
        reject("INVALID_RAW_AMOUNT")
    number = int(value)
    if not 0 < number < 2**64 or str(number) != value:
        reject("INVALID_RAW_AMOUNT")
    return number


@dataclass(frozen=True)
class Intent:
    wallet: str
    output_mint: str
    input_raw: str
    minimum_output_raw: str


def inspect_evidence(intent, policy, quote, order):
    """Caller supplies independent operator intent; quote/order are untrusted.

    No age or origin claim is made about local files. Never consume this report
    as a server authorization token. Live account evidence is a separate check.
    """
    if not isinstance(intent, Intent) or not isinstance(policy, FeePolicy):
        reject("INVALID_OPERATOR_INTENT")
    if not valid_public_key(intent.wallet) or not valid_public_key(intent.output_mint) or intent.output_mint == WSOL_MINT:
        reject("INVALID_OPERATOR_INTENT")
    input_raw = amount(intent.input_raw)
    minimum = amount(intent.minimum_output_raw)
    if not policy.enabled or type(policy.fee_bps) is not int or not 50 <= policy.fee_bps <= 255 or not valid_public_key(policy.referral_account):
        reject("FEE_TEST_POLICY_REQUIRED")
    for payload in (quote, order):
        if not isinstance(payload, dict):
            reject("INVALID_PROVIDER_EVIDENCE")
        if payload.get("inputMint") != WSOL_MINT or payload.get("outputMint") != intent.output_mint or payload.get("inAmount") != intent.input_raw:
            reject("TRADE_INTENT_MISMATCH")
        output = amount(payload.get("outAmount"))
        threshold = amount(payload.get("otherAmountThreshold"))
        if not minimum <= threshold <= output:
            reject("MINIMUM_OUTPUT_MISMATCH")
        if payload.get("gasless") not in (None, False):
            reject("GASLESS_NOT_REVIEWED")
        try:
            validate_fee_response(policy, payload, input_mint=WSOL_MINT, output_mint=intent.output_mint)
        except FeePolicyRejected:
            reject("PROVIDER_FEE_POLICY_MISMATCH")
    if quote.get("transaction") not in (None, ""):
        reject("QUOTE_CONTAINS_TRANSACTION")
    if order.get("taker") != intent.wallet:
        reject("TAKER_MISMATCH")
    try:
        raw, signatures, message, signers, accounts, instructions = _transaction_parts(order.get("transaction"))
        if any(signature != bytes(64) for signature in signatures):
            reject("SIGNED_EVIDENCE_NOT_ACCEPTED")
        # Independent fixed allowlist: an operator's production override cannot
        # broaden the harness's reviewed program universe.
        for instruction in instructions:
            if instruction.program_index >= len(accounts) or any(i >= len(accounts) for i in instruction.account_indices):
                reject("LOOKUP_ACCOUNTS_REQUIRE_RESOLUTION")
            if _base58_text(accounts[instruction.program_index]) not in DEFAULT_ALLOWED_SWAP_PROGRAMS:
                reject("UNREVIEWED_PROGRAM")
        _validate_transaction_policy(signers, accounts, instructions, _base58_bytes(intent.wallet), input_raw)
    except JupiterSwapRejected:
        reject("TRANSACTION_STRUCTURE_REJECTED")
    expected_ata = referral_token_address(policy.referral_account, WSOL_MINT)
    # Presence is diagnostic only: the program may ignore the account entirely.
    present = _base58_bytes(expected_ata) in accounts
    return {
        "status": "REVIEW_REQUIRED", "execution_ready": False,
        "fee_receipt_verified": False, "transaction_fee_verified": False,
        "structural_checks": "passed",
        "message_sha256": hashlib.sha256(message).hexdigest(),
        "policy_id": policy.fingerprint,
        "expected_wsol_ata": expected_ata,
        "expected_ata_in_static_accounts": present,
        "provider_fee_bps": policy.fee_bps,
        "blockers": ["JUPITER_INSTRUCTION_SEMANTICS_NOT_VERIFIED",
                     "FEE_AMOUNT_AND_DESTINATION_NOT_VERIFIED",
                     "LIVE_ACCOUNT_STATE_AND_SIMULATION_REQUIRED"],
        "note": "Local evidence only. Account presence and provider echoes are not fee proof.",
    }


def load_evidence(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                reject("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_EVIDENCE_BYTES + 1)
    if len(raw) > MAX_EVIDENCE_BYTES:
        reject("EVIDENCE_TOO_LARGE")
    value = json.loads(raw, object_pairs_hook=unique_pairs,
                       parse_constant=lambda _: reject("INVALID_JSON_NUMBER"))
    if not isinstance(value, dict) or set(value) != {"quote", "order"}:
        reject("INVALID_EVIDENCE_ENVELOPE")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", help="Local JSON containing quote and unsigned order")
    parser.add_argument("--wallet", required=True)
    parser.add_argument("--output-mint", required=True)
    parser.add_argument("--input-raw", required=True)
    parser.add_argument("--minimum-output-raw", required=True)
    parser.add_argument("--referral", required=True)
    parser.add_argument("--fee-bps", required=True)
    args = parser.parse_args(argv)
    try:
        # Isolated test policy; never enable or mutate process production flags.
        policy = read_fee_policy({"DEXSATO_JUPITER_FEE_ENABLED": "true",
            "DEXSATO_JUPITER_REFERRAL_ACCOUNT": args.referral,
            "DEXSATO_JUPITER_REFERRAL_FEE_BPS": args.fee_bps})
        evidence = load_evidence(args.evidence)
        result = inspect_evidence(Intent(args.wallet, args.output_mint, args.input_raw,
            args.minimum_output_raw), policy, evidence["quote"], evidence["order"])
    except HarnessRejected as error:
        print(json.dumps({"status": "REJECTED", "execution_ready": False, "reason": str(error)}))
        return 1
    except Exception:
        print(json.dumps({"status": "REJECTED", "execution_ready": False, "reason": "HARNESS_INPUT_OR_DEPENDENCY_ERROR"}))
        return 1
    print(json.dumps(result, indent=2))
    # Even structural success is nonzero: no pipeline should treat it as approval.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
