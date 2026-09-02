import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from application.jupiter_claim_v2_gate_design import CONFIRMATION_PHRASE
from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, arm_claim_gate, bind_wallet_approval, read_gate,
    require_armed_claim_gate,
)

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def closure():
    return {"status": "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED",
        "closure_id": "c" * 64, "message_sha256": "a" * 64,
        "transaction_sha256": "b" * 64, "mint": "mint",
        "referral_account": "referral", "partner": "partner",
        "gross_claim_raw": "5000", "partner_delta_raw": "4000",
        "project_admin_delta_raw": "1000",
        "claim_gate_design_eligible": True,
        "simulated_claim_split_verified": True,
        "balance_conservation_verified": True,
        "claim_execution_approved": False, "transaction_signed": False,
        "transaction_submitted": False, "claim_submitted": False,
        "execution_ready": False}


def environment(**changes):
    return {"DEXSATO_JUPITER_CLAIM_GATE_ENABLED": "true",
            "DEXSATO_JUPITER_FEE_ENABLED": "false", **changes}


def test_gate_arms_atomically_and_contains_no_transaction_material(tmp_path):
    path = tmp_path / "claim-gate.json"
    gate = arm_claim_gate(path, closure(), CONFIRMATION_PHRASE,
                          environment=environment(), current=NOW)
    assert gate["status"] == "ARMED"
    assert gate["exact_claim_raw"] == gate["maximum_claim_raw"] == "5000"
    assert gate["expected_partner_raw"] == "4000"
    assert gate["expected_project_raw"] == "1000"
    assert gate["expires_at"] == (NOW + timedelta(seconds=300)).isoformat()
    assert gate["submission_attempt_count"] == 0
    assert gate["submission_permitted"] is False
    assert gate["claim_execution_ready"] is False
    assert gate["execution_ready"] is False
    assert "transaction" not in gate
    with pytest.raises(FileExistsError):
        arm_claim_gate(path, closure(), CONFIRMATION_PHRASE,
                       environment=environment(), current=NOW)


@pytest.mark.parametrize("confirmation,env,code", [
    (CONFIRMATION_PHRASE,
     {"DEXSATO_JUPITER_CLAIM_GATE_ENABLED": "false"},
     "CLAIM_GATE_FEATURE_DISABLED"),
    (CONFIRMATION_PHRASE,
     {"DEXSATO_JUPITER_CLAIM_GATE_ENABLED": "true",
      "DEXSATO_JUPITER_FEE_ENABLED": "true"},
     "KEEP_PRODUCTION_FEES_DISABLED"),
    ("yes", environment(), "EXPLICIT_CLAIM_CONFIRMATION_REQUIRED"),
])
def test_disabled_unsafe_or_weak_confirmation_cannot_arm(
        tmp_path, confirmation, env, code):
    with pytest.raises(ClaimV2GateRejected, match=code):
        arm_claim_gate(tmp_path / "gate.json", closure(), confirmation,
                       environment=env, current=NOW)


def test_expiry_and_closure_tampering_fail_closed(tmp_path):
    path = tmp_path / "gate.json"
    arm_claim_gate(path, closure(), CONFIRMATION_PHRASE,
                   environment=environment(), current=NOW)
    with pytest.raises(ClaimV2GateRejected, match="CLAIM_GATE_EXPIRED"):
        require_armed_claim_gate(path, closure(),
            current=NOW + timedelta(seconds=301))
    changed = closure()
    changed["transaction_sha256"] = "d" * 64
    with pytest.raises(ClaimV2GateRejected,
                       match="CLAIM_GATE_CLOSURE_BINDING_MISMATCH"):
        require_armed_claim_gate(path, changed, current=NOW)


def test_wallet_digest_binds_once_and_identical_poll_is_idempotent(tmp_path):
    path = tmp_path / "gate.json"
    armed = arm_claim_gate(path, closure(), CONFIRMATION_PHRASE,
                           environment=environment(), current=NOW)
    digest = hashlib.sha256(b"signed").hexdigest()
    bound = bind_wallet_approval(path, armed["gate_id"], digest, current=NOW)
    assert bound["status"] == "WALLET_APPROVAL_BOUND"
    assert bound["wallet_review_count"] == 1
    assert bound["submission_attempt_count"] == 0
    assert bound["submission_permitted"] is False
    assert bind_wallet_approval(path, armed["gate_id"], digest,
                                current=NOW)["wallet_review_count"] == 1
    with pytest.raises(ClaimV2GateRejected, match="CLAIM_GATE_REPLAY_MISMATCH"):
        bind_wallet_approval(path, armed["gate_id"], "e" * 64, current=NOW)
    assert read_gate(path)["claim_submitted"] is False
