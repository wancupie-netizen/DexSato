import copy

import pytest

from application.jupiter_claim_v2_simulation_closure import (
    ClaimV2ClosureRejected, close_funded_simulation,
)

MESSAGE = "a" * 64
TRANSACTION = "b" * 64


def artifacts():
    identity = {"mint": "So11111111111111111111111111111111111111112",
                "referral_account": "referral", "partner": "partner"}
    capture = {"status": "SDK_UNSIGNED_CAPTURED", "sdk_version": "0.3.0",
        "message_sha256": MESSAGE, "transaction_sha256": TRANSACTION,
        "rpc_slot": 443680899, "identity": identity,
        "execution_ready": False, "fee_receipt_verified": False}
    binding = {"status": "PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED",
        "compiled_account_binding_verified": True, "sdk_version": "0.3.0",
        "message_sha256": MESSAGE, "transaction_sha256": TRANSACTION,
        "execution_ready": False, "fee_receipt_verified": False}
    auxiliary = {"status": "CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED",
        "auxiliary_instruction_semantics_verified": True,
        "message_sha256": MESSAGE, "transaction_sha256": TRANSACTION,
        "execution_ready": False, "fee_receipt_verified": False}
    simulation = {
        "status": "CLAIM_V2_SIMULATION_BALANCE_DELTA_REVIEW_REQUIRED",
        "simulation_only": True, "simulated_claim_split_verified": True,
        "balance_conservation_verified": True, "transaction_signed": False,
        "transaction_submitted": False, "claim_submitted": False,
        "production_fee_execution_enabled": False, "execution_ready": False,
        "fee_receipt_verified": False, "on_chain_receipt_verified": False,
        "message_sha256": MESSAGE, "capture_slot": 443680899,
        "simulation_slot": 443680900, "sdk_version": "0.3.0",
        "account_order_authority": "PINNED_SDK_COMPILED_IDL",
        "mint": identity["mint"], "referral_pre_raw": "5000",
        "referral_post_raw": "0", "gross_claim_raw": "5000",
        "partner_pre_source": "CREATED_ATA_IMPLICIT_ZERO",
        "partner_delta_raw": "4000", "project_admin_delta_raw": "1000",
    }
    return capture, binding, auxiliary, simulation


def test_exact_funded_simulation_closes_without_execution_authority():
    report = close_funded_simulation(*artifacts())
    assert report["status"] == "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED"
    assert len(report["closure_id"]) == 64
    assert report["gross_claim_raw"] == "5000"
    assert report["partner_delta_raw"] == "4000"
    assert report["project_admin_delta_raw"] == "1000"
    assert report["claim_gate_design_eligible"] is True
    assert report["claim_execution_approved"] is False
    assert report["transaction_signed"] is False
    assert report["transaction_submitted"] is False
    assert report["claim_submitted"] is False
    assert report["execution_ready"] is False


def test_closure_is_deterministic_and_does_not_mutate_input():
    values = artifacts()
    before = copy.deepcopy(values)
    first = close_funded_simulation(*values)
    second = close_funded_simulation(*values)
    assert first["closure_id"] == second["closure_id"]
    assert values == before


@pytest.mark.parametrize("artifact,field,value,code", [
    (0, "status", "OTHER", "FRESH_UNSIGNED_CAPTURE_REQUIRED"),
    (1, "compiled_account_binding_verified", False, "COMPILED_BINDING_REQUIRED"),
    (2, "auxiliary_instruction_semantics_verified", False,
     "AUXILIARY_ALLOWLIST_REQUIRED"),
    (3, "message_sha256", "c" * 64, "SIMULATION_MESSAGE_BINDING_MISMATCH"),
    (3, "simulation_slot", 443680898, "SIMULATION_SLOT_MISMATCH"),
    (3, "referral_pre_raw", "4999", "FUNDED_CLAIM_DELTA_MISMATCH"),
    (3, "partner_delta_raw", "3999", "FUNDED_CLAIM_DELTA_MISMATCH"),
    (3, "project_admin_delta_raw", "999", "FUNDED_CLAIM_DELTA_MISMATCH"),
    (3, "partner_pre_source", "RPC_TOKEN_BALANCE",
     "PARTNER_ATA_LIFECYCLE_EVIDENCE_REQUIRED"),
])
def test_every_evidence_binding_mismatch_fails_closed(artifact, field, value, code):
    values = list(artifacts())
    values[artifact][field] = value
    with pytest.raises(ClaimV2ClosureRejected, match=code):
        close_funded_simulation(*values)


@pytest.mark.parametrize("field", [
    "transaction_signed", "transaction_submitted", "claim_submitted",
    "production_fee_execution_enabled", "execution_ready",
    "fee_receipt_verified", "on_chain_receipt_verified",
])
def test_execution_or_submission_claims_are_rejected(field):
    values = list(artifacts())
    values[3][field] = True
    with pytest.raises(ClaimV2ClosureRejected,
                       match="EXECUTION_EVIDENCE_FORBIDDEN"):
        close_funded_simulation(*values)
