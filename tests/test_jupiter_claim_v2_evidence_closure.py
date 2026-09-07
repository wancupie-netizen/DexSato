import copy
from datetime import datetime, timezone

import pytest

from application import jupiter_claim_v2_evidence_closure as audit

NOW = datetime(2026, 9, 7, 5, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64


def gate():
    return {
        "status": "WALLET_APPROVAL_BOUND", "gate_id": "gate",
        "closure_id": HASH_A, "message_sha256": HASH_B,
        "signed_transaction_sha256": "c" * 64, "mint": "mint",
        "referral_account": "referral", "partner": "partner",
        "exact_claim_raw": "5000", "maximum_claim_raw": "5000",
        "expected_partner_raw": "4000", "expected_project_raw": "1000",
        "wallet_review_count": 1, "approval_count": 0,
        "submission_attempt_count": 0, "submission_permitted": False,
        "live_claim_approved": False, "claim_submitted": False,
        "execution_ready": False,
    }


def evidence():
    return {
        "status": "CLAIM_V2_WALLET_SIGNED_HASH_INDEPENDENTLY_VERIFIED",
        "gate_id": "gate", "closure_id": HASH_A,
        "message_sha256": HASH_B, "capture_message_sha256": HASH_B,
        "signed_transaction_sha256": "c" * 64,
        "independent_hash_verified": True,
        "wallet_signature_verified": True,
        "signed_transaction_persisted": False,
        "rpc_freshness_verified": False,
        "live_reconstruction_required": True,
    }


def closed():
    return audit.close_signed_evidence(gate(), evidence(),
        environment={}, current=NOW)


def test_exact_hash_only_evidence_closes_without_authorizing_execution():
    report = closed()
    assert report["status"] == "CLAIM_V2_SIGNED_EVIDENCE_CLOSED"
    assert report["source_gate_reusable"] is False
    assert report["prior_signed_transaction_reusable"] is False
    assert report["signed_transaction_persisted"] is False
    assert report["live_reconstruction_required"] is True
    assert report["live_claim_approved"] is False
    assert report["submission_permitted"] is False
    assert report["submission_attempt_count"] == 0
    assert report["execution_ready"] is False


@pytest.mark.parametrize("target,key,value,reason", [
    ("gate", "status", "LIVE_CLAIM_APPROVED", "WALLET_BOUND_GATE_REQUIRED"),
    ("gate", "signed_transaction_sha256", "d" * 64,
     "GATE_EVIDENCE_SIGNED_HASH_MISMATCH"),
    ("gate", "approval_count", 1, "UNSAFE_OR_USED_SOURCE_GATE"),
    ("gate", "submission_attempt_count", 1, "UNSAFE_OR_USED_SOURCE_GATE"),
    ("evidence", "message_sha256", "d" * 64,
     "GATE_EVIDENCE_MESSAGE_MISMATCH"),
    ("evidence", "wallet_signature_verified", False,
     "SIGNED_EVIDENCE_POLICY_MISMATCH"),
])
def test_closure_mismatches_fail_closed(target, key, value, reason):
    gate_value, evidence_value = gate(), evidence()
    (gate_value if target == "gate" else evidence_value)[key] = value
    with pytest.raises(audit.ClaimV2EvidenceClosureRejected, match=reason):
        audit.close_signed_evidence(gate_value, evidence_value,
            environment={}, current=NOW)


@pytest.mark.parametrize("flag", audit.FALSE_FLAGS)
def test_closure_rejects_every_execution_flag(flag):
    with pytest.raises(audit.ClaimV2EvidenceClosureRejected,
                       match="KEEP_CLAIM_EXECUTION_DISABLED"):
        audit.close_signed_evidence(gate(), evidence(),
            environment={flag: "true"}, current=NOW)


def test_closure_id_is_deterministic_but_timestamp_is_not_identity():
    first = closed()
    second = audit.close_signed_evidence(gate(), evidence(), environment={},
        current=datetime(2026, 9, 7, 6, 0, tzinfo=timezone.utc))
    assert first["evidence_closure_id"] == second["evidence_closure_id"]
    assert first["closed_at"] != second["closed_at"]


def test_fresh_reconstruction_design_never_reuses_old_material():
    report = audit.design_fresh_reconstruction(closed(), environment={})
    assert report["status"] == \
        "CLAIM_V2_FRESH_RECONSTRUCTION_BOUNDARY_REVIEW_REQUIRED"
    required = (
        "fresh_rpc_mainnet_verification_required",
        "fresh_funded_balance_verification_required",
        "fresh_blockhash_required", "fresh_unsigned_capture_required",
        "fresh_simulation_closure_required", "fresh_gate_required",
        "fresh_wallet_signature_required",
    )
    assert all(report[key] is True for key in required)
    assert report["prior_message_reusable"] is False
    assert report["prior_signed_transaction_reusable"] is False
    assert report["transaction_constructed"] is False
    assert report["transaction_signed"] is False
    assert report["live_claim_approved"] is False
    assert report["submission_permitted"] is False
    assert report["execution_ready"] is False


def test_design_rejects_mutated_or_unsafe_closure():
    for key, value in (("source_gate_reusable", True),
                       ("prior_signed_transaction_reusable", True)):
        value_closure = copy.deepcopy(closed())
        value_closure[key] = value
        with pytest.raises(audit.ClaimV2EvidenceClosureRejected):
            audit.design_fresh_reconstruction(value_closure, environment={})
    value_closure = closed()
    value_closure["live_claim_approved"] = True
    with pytest.raises(audit.ClaimV2EvidenceClosureRejected,
                       match="UNSAFE_SIGNED_EVIDENCE_CLOSURE"):
        audit.design_fresh_reconstruction(value_closure, environment={})


def test_source_contains_no_signing_approval_submission_or_rpc_api():
    source = open(audit.__file__, encoding="utf-8").read()
    forbidden = ("requests", "SOLANA_RPC_URL", "signTransaction",
                 "approve_live_claim", "submit_claim", "sendTransaction",
                 "reserve_submission", "private_key", "secret_key")
    assert all(term not in source for term in forbidden)
