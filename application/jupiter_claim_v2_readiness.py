"""Fail-closed ClaimV2 closure and monetization-readiness decision.

This module evaluates bounded, normalized audit evidence only.  It never reads
wallet keys, contacts RPC, builds transactions, signs, submits, or claims.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_JSON_BYTES = 262_144
EXPECTED_SOURCE_COMMIT = "6500f64ff004e78faa15d66446e175ede625260d"
EXPECTED_SDK_VERSION = "0.3.0"
EXPECTED_ACCOUNT_ORDER = "PINNED_SDK_COMPILED_IDL"
FINALIZED_SWAP_STATUS = "FINALIZED_VERIFIED"
VERIFIED_SIMULATION_STATUS = "CLAIM_V2_SIMULATION_BALANCE_DELTA_REVIEW_REQUIRED"


class ClaimV2ReadinessRejected(ValueError):
    """Fixed public rejection code; supplied evidence is never echoed."""


def require(condition, code):
    if not condition:
        raise ClaimV2ReadinessRejected(code)


def _false(value):
    return value is False


def _raw_amount(value, *, positive=False):
    require(type(value) is str and value.isdigit() and len(value) <= 40,
            "INVALID_RAW_AMOUNT")
    amount = int(value)
    require(0 <= amount < 2**64 and (not positive or amount > 0),
            "INVALID_RAW_AMOUNT")
    return amount


def _bounded_dict(value, code):
    require(type(value) is dict and len(value) <= 64, code)
    return value


def _accrual_verified(receipt):
    receipt = _bounded_dict(receipt, "INVALID_FEE_RECEIPT_EVIDENCE")
    require(receipt.get("status") == FINALIZED_SWAP_STATUS,
            "FINALIZED_FEE_RECEIPT_REQUIRED")
    require(receipt.get("fee_receipt_verified") is True,
            "FINALIZED_FEE_RECEIPT_REQUIRED")
    require(_false(receipt.get("execution_ready")),
            "EXECUTION_READY_EVIDENCE_FORBIDDEN")
    delta = _raw_amount(receipt.get("referral_delta_raw"), positive=True)
    require(delta == 5000, "VERIFIED_REFERRAL_DELTA_MISMATCH")
    signature = receipt.get("signature")
    require(type(signature) is str and 64 <= len(signature) <= 96,
            "INVALID_FINALIZED_SIGNATURE")
    slot = receipt.get("finalized_slot")
    require(type(slot) is int and slot > 0, "INVALID_FINALIZED_SLOT")
    return delta


def _semantics_verified(semantics):
    semantics = _bounded_dict(semantics, "INVALID_CLAIM_SEMANTICS_EVIDENCE")
    require(semantics.get("status") == "CLAIM_V2_SOURCE_ACCOUNT_REVIEW_REQUIRED"
            and semantics.get("source_semantics_verified") is True,
            "CLAIM_SEMANTICS_EVIDENCE_REQUIRED")
    require(semantics.get("source_commit") == EXPECTED_SOURCE_COMMIT
            and semantics.get("pinned_sdk_version") == EXPECTED_SDK_VERSION
            and semantics.get("account_order_authority") == EXPECTED_ACCOUNT_ORDER,
            "PINNED_CLAIM_CONTRACT_MISMATCH")
    require(semantics.get("account_count") == 12,
            "CLAIM_ACCOUNT_COUNT_MISMATCH")
    require(_false(semantics.get("claim_submitted"))
            and _false(semantics.get("execution_ready")),
            "CLAIM_EXECUTION_EVIDENCE_FORBIDDEN")


def _capture_verified(capture, auxiliary):
    capture = _bounded_dict(capture, "INVALID_CLAIM_CAPTURE_EVIDENCE")
    auxiliary = _bounded_dict(auxiliary, "INVALID_AUXILIARY_EVIDENCE")
    require(capture.get("status") == "SDK_UNSIGNED_CAPTURED"
            and capture.get("sdk_version") == EXPECTED_SDK_VERSION,
            "PINNED_UNSIGNED_CAPTURE_REQUIRED")
    require(_false(capture.get("execution_ready"))
            and _false(capture.get("fee_receipt_verified")),
            "CLAIM_EXECUTION_EVIDENCE_FORBIDDEN")
    require(auxiliary.get("status") ==
            "CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED"
            and auxiliary.get("auxiliary_instruction_semantics_verified") is True,
            "AUXILIARY_ALLOWLIST_EVIDENCE_REQUIRED")
    require(_false(auxiliary.get("execution_ready"))
            and _false(auxiliary.get("fee_receipt_verified")),
            "CLAIM_EXECUTION_EVIDENCE_FORBIDDEN")
    message_hash = capture.get("message_sha256")
    transaction_hash = capture.get("transaction_sha256")
    require(type(message_hash) is str and len(message_hash) == 64
            and type(transaction_hash) is str and len(transaction_hash) == 64,
            "INVALID_CAPTURE_HASH")
    require(auxiliary.get("message_sha256") == message_hash
            and auxiliary.get("transaction_sha256") == transaction_hash,
            "CAPTURE_AUXILIARY_HASH_MISMATCH")


def _simulation_result(simulation):
    simulation = _bounded_dict(simulation, "INVALID_CLAIM_SIMULATION_EVIDENCE")
    if simulation.get("status") != VERIFIED_SIMULATION_STATUS:
        return False, "READ_ONLY_CLAIM_SIMULATION_REQUIRED"
    required_true = (
        "simulation_only", "simulated_claim_split_verified",
        "balance_conservation_verified",
    )
    if not all(simulation.get(key) is True for key in required_true):
        return False, "CLAIM_SPLIT_OR_CONSERVATION_NOT_VERIFIED"
    required_false = (
        "transaction_signed", "transaction_submitted", "claim_submitted",
        "production_fee_execution_enabled", "execution_ready",
        "fee_receipt_verified", "on_chain_receipt_verified",
    )
    if not all(_false(simulation.get(key)) for key in required_false):
        raise ClaimV2ReadinessRejected("CLAIM_EXECUTION_EVIDENCE_FORBIDDEN")
    gross = _raw_amount(simulation.get("gross_claim_raw"), positive=True)
    partner = _raw_amount(simulation.get("partner_delta_raw"))
    project = _raw_amount(simulation.get("project_admin_delta_raw"))
    if partner != gross * 8000 // 10_000 or project != gross - partner:
        return False, "CLAIM_SPLIT_ARITHMETIC_MISMATCH"
    if gross != partner + project:
        return False, "CLAIM_BALANCE_CONSERVATION_MISMATCH"
    return True, None


def assess_claim_v2_readiness(evidence):
    """Return a closure decision that can never authorize execution."""
    evidence = _bounded_dict(evidence, "INVALID_READINESS_EVIDENCE")
    require(set(evidence) == {"fee_receipt", "claim_semantics", "unsigned_capture",
                              "auxiliary_audit", "claim_simulation",
                              "dependency_attestation"},
            "INVALID_READINESS_EVIDENCE_FIELDS")
    delta = _accrual_verified(evidence["fee_receipt"])
    _semantics_verified(evidence["claim_semantics"])
    _capture_verified(evidence["unsigned_capture"], evidence["auxiliary_audit"])
    dependency = _bounded_dict(evidence["dependency_attestation"],
                               "INVALID_DEPENDENCY_ATTESTATION")
    require(dependency.get("isolated_capture_only") is True
            and dependency.get("production_runtime_approved") is False
            and dependency.get("live_claim_approved") is False,
            "DEPENDENCY_ISOLATION_ATTESTATION_REQUIRED")
    simulation_verified, blocker = _simulation_result(evidence["claim_simulation"])
    status = ("ACCRUAL_AND_READ_ONLY_CLAIM_SIMULATION_VERIFIED"
              if simulation_verified else "ACCRUAL_READY_CLAIM_NOT_READY")
    blockers = [] if simulation_verified else [blocker]
    # Even a verified simulation remains evidence, never live-claim approval.
    blockers.append("LIVE_CLAIM_APPROVAL_GATE_REQUIRED")
    return {
        "status": status,
        "closure_decision": "MONETIZATION_ACCRUAL_VERIFIED",
        "fee_accrual_verified": True,
        "referral_delta_raw": str(delta),
        "claim_semantics_verified": True,
        "compiled_account_order_verified": True,
        "unsigned_capture_verified": True,
        "auxiliary_allowlist_verified": True,
        "claim_simulation_verified": simulation_verified,
        "dependency_isolated_capture_only": True,
        "claim_execution_approved": False,
        "claim_execution_ready": False,
        "production_fee_execution_enabled": False,
        "execution_ready": False,
        "fee_receipt_verified": True,
        "decision_blockers": blockers,
        "note": "Fee accrual proof is not ClaimV2 execution approval.",
    }


def _strict_json(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= MAX_JSON_BYTES, "READINESS_JSON_TOO_LARGE")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_READINESS_JSON_KEY")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8-sig"),
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except ClaimV2ReadinessRejected:
        raise
    except Exception:
        raise ClaimV2ReadinessRejected("INVALID_READINESS_JSON") from None
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    try:
        require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
        report = assess_claim_v2_readiness(_strict_json(args.evidence))
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: report[key] for key in
            ("status", "claim_execution_ready", "execution_ready")}))
        return 2
    except ClaimV2ReadinessRejected as error:
        reason = str(error)
    except Exception:
        reason = "READINESS_INPUT_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status": "CLAIM_V2_READINESS_NOT_VERIFIED",
                      "reason": reason, "claim_execution_ready": False,
                      "execution_ready": False, "fee_receipt_verified": False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
