import inspect

import pytest

from application import jupiter_claim_v2_gate_design as gate
from application.jupiter_claim_v2_gate_design import (
    ClaimV2GateDesignRejected, design_one_shot_claim_gate,
)


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


def test_design_binds_exact_evidence_but_implements_nothing():
    report = design_one_shot_claim_gate(closure())
    assert report["status"] == "CLAIM_V2_ONE_SHOT_GATE_DESIGN_REVIEW_REQUIRED"
    assert report["implementation_mode"] == "DESIGN_ONLY"
    assert report["exact_claim_raw"] == report["maximum_claim_raw"] == "5000"
    assert report["expected_partner_raw"] == "4000"
    assert report["expected_project_raw"] == "1000"
    assert report["proposed_ttl_seconds"] == 300
    assert report["planned_states"][0] == "DESIGN_ONLY"
    assert report["required_terminal_receipt"] == "FINALIZED_VERIFIED"
    assert report["persistence_implemented"] is False
    assert report["arming_implemented"] is False
    assert report["wallet_signing_implemented"] is False
    assert report["transaction_submission_implemented"] is False
    assert report["live_claim_approved"] is False
    assert report["claim_execution_ready"] is False
    assert report["execution_ready"] is False


@pytest.mark.parametrize("field,value,code", [
    ("closure_id", "bad", "INVALID_CLOSURE_HASH"),
    ("message_sha256", "d" * 63, "INVALID_CLOSURE_HASH"),
    ("gross_claim_raw", "5001", "CLAIM_AMOUNT_OR_SPLIT_MISMATCH"),
    ("partner_delta_raw", "5000", "CLAIM_AMOUNT_OR_SPLIT_MISMATCH"),
    ("claim_gate_design_eligible", False, "VERIFIED_SIMULATION_CLOSURE_REQUIRED"),
    ("claim_execution_approved", True, "EXECUTION_EVIDENCE_FORBIDDEN"),
    ("transaction_signed", True, "EXECUTION_EVIDENCE_FORBIDDEN"),
    ("transaction_submitted", True, "EXECUTION_EVIDENCE_FORBIDDEN"),
    ("claim_submitted", True, "EXECUTION_EVIDENCE_FORBIDDEN"),
    ("execution_ready", True, "EXECUTION_EVIDENCE_FORBIDDEN"),
])
def test_tampering_and_execution_authority_fail_closed(field, value, code):
    value_set = closure()
    value_set[field] = value
    with pytest.raises(ClaimV2GateDesignRejected, match=code):
        design_one_shot_claim_gate(value_set)


def test_module_has_no_operational_claim_gate_api_or_network_dependency():
    public = {name for name, value in vars(gate).items()
              if callable(value) and not name.startswith("_")}
    assert not public.intersection({"arm", "bind", "consume", "sign", "submit",
                                    "send", "execute", "claim"})
    source = inspect.getsource(gate)
    for forbidden in ("requests", "urllib", "solders", "Keypair",
                      "sendTransaction", "sendRawTransaction", "secretKey"):
        assert forbidden not in source
