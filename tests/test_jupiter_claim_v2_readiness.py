import copy

import pytest

from application.jupiter_claim_v2_readiness import (
    ClaimV2ReadinessRejected, assess_claim_v2_readiness,
)

HASH_A = "a" * 64
HASH_B = "b" * 64


def evidence(*, simulation_verified=False):
    simulation = {
        "status": "CLAIM_V2_SIMULATION_NOT_VERIFIED",
        "reason": "REFERRAL_SOURCE_DELTA_INVALID",
        "execution_ready": False,
        "fee_receipt_verified": False,
    }
    if simulation_verified:
        simulation = {
            "status": "CLAIM_V2_SIMULATION_BALANCE_DELTA_REVIEW_REQUIRED",
            "simulation_only": True,
            "transaction_signed": False,
            "transaction_submitted": False,
            "claim_submitted": False,
            "production_fee_execution_enabled": False,
            "execution_ready": False,
            "fee_receipt_verified": False,
            "on_chain_receipt_verified": False,
            "simulated_claim_split_verified": True,
            "balance_conservation_verified": True,
            "gross_claim_raw": "5000",
            "partner_delta_raw": "4000",
            "project_admin_delta_raw": "1000",
        }
    return {
        "fee_receipt": {
            "status": "FINALIZED_VERIFIED",
            "fee_receipt_verified": True,
            "execution_ready": False,
            "referral_delta_raw": "5000",
            "signature": "3" * 88,
            "finalized_slot": 443580807,
        },
        "claim_semantics": {
            "status": "CLAIM_V2_SOURCE_ACCOUNT_REVIEW_REQUIRED",
            "source_semantics_verified": True,
            "source_commit": "6500f64ff004e78faa15d66446e175ede625260d",
            "pinned_sdk_version": "0.3.0",
            "account_order_authority": "PINNED_SDK_COMPILED_IDL",
            "account_count": 12,
            "claim_submitted": False,
            "execution_ready": False,
        },
        "unsigned_capture": {
            "status": "SDK_UNSIGNED_CAPTURED",
            "sdk_version": "0.3.0",
            "message_sha256": HASH_A,
            "transaction_sha256": HASH_B,
            "execution_ready": False,
            "fee_receipt_verified": False,
        },
        "auxiliary_audit": {
            "status": "CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED",
            "auxiliary_instruction_semantics_verified": True,
            "message_sha256": HASH_A,
            "transaction_sha256": HASH_B,
            "execution_ready": False,
            "fee_receipt_verified": False,
        },
        "claim_simulation": simulation,
        "dependency_attestation": {
            "isolated_capture_only": True,
            "production_runtime_approved": False,
            "live_claim_approved": False,
        },
    }


def test_current_evidence_closes_accrual_but_not_claim_execution():
    report = assess_claim_v2_readiness(evidence())
    assert report["status"] == "ACCRUAL_READY_CLAIM_NOT_READY"
    assert report["fee_accrual_verified"] is True
    assert report["referral_delta_raw"] == "5000"
    assert report["claim_simulation_verified"] is False
    assert report["decision_blockers"] == [
        "READ_ONLY_CLAIM_SIMULATION_REQUIRED",
        "LIVE_CLAIM_APPROVAL_GATE_REQUIRED",
    ]
    assert report["claim_execution_approved"] is False
    assert report["claim_execution_ready"] is False
    assert report["execution_ready"] is False


def test_verified_simulation_still_never_approves_live_claim():
    report = assess_claim_v2_readiness(evidence(simulation_verified=True))
    assert report["status"] == "ACCRUAL_AND_READ_ONLY_CLAIM_SIMULATION_VERIFIED"
    assert report["claim_simulation_verified"] is True
    assert report["decision_blockers"] == ["LIVE_CLAIM_APPROVAL_GATE_REQUIRED"]
    assert report["claim_execution_approved"] is False
    assert report["claim_execution_ready"] is False
    assert report["production_fee_execution_enabled"] is False


@pytest.mark.parametrize("path,value", [
    (("fee_receipt", "status"), "FINALIZATION_PENDING"),
    (("fee_receipt", "fee_receipt_verified"), False),
    (("fee_receipt", "referral_delta_raw"), "4000"),
    (("claim_semantics", "source_commit"), "0" * 40),
    (("claim_semantics", "account_count"), 11),
    (("unsigned_capture", "sdk_version"), "latest"),
    (("auxiliary_audit", "message_sha256"), "c" * 64),
    (("dependency_attestation", "production_runtime_approved"), True),
])
def test_identity_and_policy_mismatches_fail_closed(path, value):
    item = evidence()
    item[path[0]][path[1]] = value
    with pytest.raises(ClaimV2ReadinessRejected):
        assess_claim_v2_readiness(item)


@pytest.mark.parametrize("field", [
    "transaction_signed", "transaction_submitted", "claim_submitted",
    "production_fee_execution_enabled", "execution_ready",
    "fee_receipt_verified", "on_chain_receipt_verified",
])
def test_simulation_cannot_smuggle_execution_approval(field):
    item = evidence(simulation_verified=True)
    item["claim_simulation"][field] = True
    with pytest.raises(ClaimV2ReadinessRejected,
                       match="CLAIM_EXECUTION_EVIDENCE_FORBIDDEN"):
        assess_claim_v2_readiness(item)


def test_split_arithmetic_mismatch_remains_not_ready():
    item = evidence(simulation_verified=True)
    item["claim_simulation"]["partner_delta_raw"] = "3999"
    report = assess_claim_v2_readiness(item)
    assert report["claim_simulation_verified"] is False
    assert report["decision_blockers"][0] == "CLAIM_SPLIT_ARITHMETIC_MISMATCH"


def test_input_is_not_mutated():
    item = evidence()
    before = copy.deepcopy(item)
    assess_claim_v2_readiness(item)
    assert item == before
