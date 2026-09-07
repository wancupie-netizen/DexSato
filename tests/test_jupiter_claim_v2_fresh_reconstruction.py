import copy
import json
from pathlib import Path

import pytest

from application import jupiter_claim_v2_fresh_reconstruction as fresh
from application.jupiter_claim_v2_evidence_closure import (
    design_fresh_reconstruction,
)

SAFE_ENV = {
    "DEXSATO_JUPITER_FEE_ENABLED": "false",
    "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED": "false",
    "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED": "false",
    "DEXSATO_JUPITER_CLAIM_GATE_ENABLED": "true",
}
OLD_MESSAGE = "a" * 64
NEW_MESSAGE = "b" * 64
NEW_TRANSACTION = "c" * 64
OLD_SIMULATION = "d" * 64
NEW_SIMULATION = "e" * 64


def evidence_closure():
    return {
        "status": "CLAIM_V2_SIGNED_EVIDENCE_CLOSED",
        "evidence_closure_id": "f" * 64,
        "source_gate_id": "retired-gate",
        "simulation_closure_id": OLD_SIMULATION,
        "message_sha256": OLD_MESSAGE,
        "signed_transaction_sha256": "1" * 64,
        "exact_claim_raw": "5000", "expected_partner_raw": "4000",
        "expected_project_raw": "1000", "source_gate_reusable": False,
        "prior_signed_transaction_reusable": False,
        "live_reconstruction_required": True, "live_claim_approved": False,
        "submission_permitted": False, "submission_attempt_count": 0,
        "claim_submitted": False, "execution_ready": False,
    }


def boundary():
    return design_fresh_reconstruction(evidence_closure(), environment={})


def test_plan_exactly_binds_f6c5_closure_and_disables_execution():
    report = fresh.verify_reconstruction_plan(
        evidence_closure(), boundary(), environment={})
    assert report["status"] == "CLAIM_V2_FRESH_RECONSTRUCTION_PLAN_VERIFIED"
    assert report["retired_source_gate_id"] == "retired-gate"
    assert report["prior_gate_reusable"] is False
    assert report["transaction_constructed"] is False
    assert report["transaction_signed"] is False
    assert report["live_claim_approved"] is False
    assert report["submission_permitted"] is False
    assert report["execution_ready"] is False


def test_boundary_mutation_fails_before_generation(tmp_path):
    changed = boundary()
    changed["fresh_blockhash_required"] = False
    with pytest.raises(fresh.ClaimV2FreshReconstructionRejected,
                       match="RECONSTRUCTION_BOUNDARY_MISMATCH"):
        fresh.prepare_fresh_reconstruction({}, evidence_closure(), changed,
            tmp_path / "fresh", tmp_path / "gate.json", "confirm",
            environment=SAFE_ENV,
            generator=lambda *args, **kwargs: pytest.fail("must not generate"))


def test_prepare_generates_new_unapproved_material_and_exact_review_copy(tmp_path):
    output = tmp_path / "fresh"
    gate_path = tmp_path / "gate.json"

    capture = {"status": "SDK_UNSIGNED_CAPTURED",
        "message_sha256": NEW_MESSAGE, "transaction_sha256": NEW_TRANSACTION,
        "rpc_slot": 123, "execution_ready": False}
    simulation = {"status": "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED",
        "closure_id": NEW_SIMULATION, "message_sha256": NEW_MESSAGE,
        "transaction_sha256": NEW_TRANSACTION, "gross_claim_raw": "5000",
        "partner_delta_raw": "4000", "project_admin_delta_raw": "1000",
        "claim_execution_approved": False}
    gate = {"status": "ARMED", "gate_id": "fresh-gate",
        "closure_id": NEW_SIMULATION, "message_sha256": NEW_MESSAGE,
        "unsigned_transaction_sha256": NEW_TRANSACTION,
        "wallet_review_count": 0, "approval_count": 0,
        "submission_attempt_count": 0, "submission_permitted": False,
        "live_claim_approved": False, "claim_submitted": False,
        "execution_ready": False}

    def generator(identity, output_dir, target_gate, confirmation, **kwargs):
        output_dir.mkdir()
        (output_dir / "unsigned_claim_v2_capture.json").write_text(
            json.dumps(capture), encoding="utf-8")
        (output_dir / "claim_v2_simulation_closure.json").write_text(
            json.dumps(simulation), encoding="utf-8")
        target_gate.write_text(json.dumps(gate), encoding="utf-8")
        return {"status": "FRESH_CLAIM_V2_ARTIFACTS_REVIEW_REQUIRED",
            "closure_id": NEW_SIMULATION, "gate_id": "fresh-gate",
            "artifact_count": 5, "wallet_signature_verified": False,
            "live_claim_approved": False, "submission_attempt_count": 0,
            "transaction_submitted": False, "claim_submitted": False,
            "execution_ready": False}

    report = fresh.prepare_fresh_reconstruction(
        {"payer": "wallet"}, evidence_closure(), boundary(), output,
        gate_path, "confirm", environment=SAFE_ENV, generator=generator,
        gate_reader=lambda path: gate)
    assert report["status"] == \
        "CLAIM_V2_FRESH_RECONSTRUCTION_PREPARED_REVIEW_REQUIRED"
    assert report["fresh_gate_id"] == "fresh-gate"
    assert report["prior_gate_reused"] is False
    assert report["prior_message_reused"] is False
    assert report["transaction_constructed"] is True
    assert report["transaction_signed"] is False
    assert report["live_claim_approved"] is False
    assert report["submission_permitted"] is False
    assert report["submission_attempt_count"] == 0
    assert (output / "claim_v2_gate_review.json").read_bytes() == \
        gate_path.read_bytes()


@pytest.mark.parametrize("mutation,reason", [
    (("capture", "message_sha256", OLD_MESSAGE), "PRIOR_CLAIM_MATERIAL_REUSED"),
    (("simulation", "closure_id", OLD_SIMULATION),
     "PRIOR_CLAIM_MATERIAL_REUSED"),
    (("gate", "gate_id", "retired-gate"), "PRIOR_CLAIM_MATERIAL_REUSED"),
    (("gate", "approval_count", 1), "FRESH_GATE_INVALID_OR_UNSAFE"),
])
def test_prepare_rejects_reuse_and_unsafe_gate(monkeypatch, tmp_path,
                                                mutation, reason):
    values = {
        "capture": {"status": "SDK_UNSIGNED_CAPTURED",
            "message_sha256": NEW_MESSAGE, "transaction_sha256": NEW_TRANSACTION,
            "rpc_slot": 123, "execution_ready": False},
        "simulation": {"status": "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED",
            "closure_id": NEW_SIMULATION, "message_sha256": NEW_MESSAGE,
            "transaction_sha256": NEW_TRANSACTION, "gross_claim_raw": "5000",
            "partner_delta_raw": "4000", "project_admin_delta_raw": "1000",
            "claim_execution_approved": False},
        "gate": {"status": "ARMED", "gate_id": "fresh-gate",
            "closure_id": NEW_SIMULATION, "message_sha256": NEW_MESSAGE,
            "unsigned_transaction_sha256": NEW_TRANSACTION,
            "wallet_review_count": 0, "approval_count": 0,
            "submission_attempt_count": 0, "submission_permitted": False,
            "live_claim_approved": False, "claim_submitted": False,
            "execution_ready": False},
    }
    group, key, value = mutation
    values[group][key] = value
    if group == "capture" and key == "message_sha256":
        values["simulation"]["message_sha256"] = value
        values["gate"]["message_sha256"] = value
    if group == "simulation" and key == "closure_id":
        values["gate"]["closure_id"] = value
    if group == "gate" and key == "gate_id":
        generated_gate_id = value
    else:
        generated_gate_id = values["gate"]["gate_id"]

    def generator(identity, output, gate_path, confirmation, **kwargs):
        output.mkdir(); gate_path.write_text("{}")
        return {"status": "FRESH_CLAIM_V2_ARTIFACTS_REVIEW_REQUIRED",
            "closure_id": values["simulation"]["closure_id"],
            "gate_id": generated_gate_id, "artifact_count": 5,
            "wallet_signature_verified": False, "live_claim_approved": False,
            "submission_attempt_count": 0, "transaction_submitted": False,
            "claim_submitted": False, "execution_ready": False}

    def reader(path):
        return (values["capture"] if Path(path).name ==
                "unsigned_claim_v2_capture.json" else values["simulation"])

    with pytest.raises(fresh.ClaimV2FreshReconstructionRejected, match=reason):
        fresh.prepare_fresh_reconstruction({}, evidence_closure(), boundary(),
            tmp_path / "fresh", tmp_path / "gate.json", "confirm",
            environment=SAFE_ENV, generator=generator, json_reader=reader,
            gate_reader=lambda path: values["gate"],
            gate_review_writer=lambda *args: pytest.fail("must not copy"))


@pytest.mark.parametrize("flag", fresh.FALSE_FLAGS)
def test_every_execution_flag_stops_before_generation(flag, tmp_path):
    env = dict(SAFE_ENV); env[flag] = "true"
    with pytest.raises(fresh.ClaimV2FreshReconstructionRejected,
                       match="KEEP_CLAIM_EXECUTION_DISABLED"):
        fresh.prepare_fresh_reconstruction({}, evidence_closure(), boundary(),
            tmp_path / "fresh", tmp_path / "gate", "confirm", environment=env,
            generator=lambda *args, **kwargs: pytest.fail("must not generate"))


def test_module_has_no_signing_approval_submission_or_secret_operation():
    source = Path(fresh.__file__).read_text(encoding="utf-8")
    forbidden = ("signTransaction", "approve_live_claim", "submit_claim",
                 "sendTransaction", "reserve_submission", "private_key",
                 "secret_key", "seed_phrase")
    assert all(term not in source for term in forbidden)
