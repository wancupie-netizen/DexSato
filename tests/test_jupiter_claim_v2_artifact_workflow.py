import hashlib
from pathlib import Path

import pytest

from application import jupiter_claim_v2_artifact_workflow as workflow


SAFE_ENV = {
    "DEXSATO_JUPITER_FEE_ENABLED": "false",
    "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED": "false",
    "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED": "false",
    "DEXSATO_JUPITER_CLAIM_GATE_ENABLED": "true",
}


def test_generate_writes_five_review_artifacts_and_unapproved_gate(tmp_path):
    calls = []
    capture = {"status": "SDK_UNSIGNED_CAPTURED", "message_sha256": "a" * 64,
               "transaction_sha256": "b" * 64}
    binding = {"status": "PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED"}
    auxiliary = {"status": "CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED"}
    simulation = {"status": "CLAIM_V2_SIMULATION_BALANCE_DELTA_REVIEW_REQUIRED"}
    closure = {"closure_id": "c" * 64}

    def sdk(identity, **kwargs):
        calls.append("sdk")
        return capture, binding

    def aux(first, second):
        calls.append("auxiliary")
        return auxiliary

    def simulate(*args, **kwargs):
        calls.append("simulation")
        return simulation

    def close(*args):
        calls.append("closure")
        return closure

    def arm(path, report, confirmation, **kwargs):
        calls.append("gate")
        assert confirmation == workflow.CONFIRMATION_PHRASE
        workflow._write_json(path, {"gate_id": "gate", "status": "ARMED",
                                    "approval_count": 0,
                                    "submission_attempt_count": 0})
        return {"gate_id": "gate"}

    output = tmp_path / "fresh"
    gate = tmp_path / "gate.json"
    report = workflow.generate_fresh_artifacts(
        {"payer": "wallet"}, output, gate, workflow.CONFIRMATION_PHRASE,
        environment=SAFE_ENV, sdk_runner=sdk, auxiliary_runner=aux,
        simulation_runner=simulate, closure_runner=close, gate_runner=arm,
    )
    assert calls == ["sdk", "auxiliary", "simulation", "closure", "gate"]
    assert sorted(path.name for path in output.iterdir()) == sorted(workflow.ARTIFACT_NAMES.values())
    assert report["status"] == "FRESH_CLAIM_V2_ARTIFACTS_REVIEW_REQUIRED"
    assert report["live_claim_approved"] is False
    assert report["transaction_submitted"] is False
    assert report["execution_ready"] is False


@pytest.mark.parametrize("collision", ["output", "gate"])
def test_generate_collision_stops_before_sdk(tmp_path, collision):
    output = tmp_path / "fresh"
    gate = tmp_path / "gate.json"
    (output.mkdir() if collision == "output" else gate.write_text("{}"))
    with pytest.raises(workflow.ClaimV2ArtifactWorkflowRejected):
        workflow.generate_fresh_artifacts(
            {}, output, gate, workflow.CONFIRMATION_PHRASE,
            environment=SAFE_ENV,
            sdk_runner=lambda *args, **kwargs: pytest.fail("SDK must not run"),
        )


def test_bind_persists_only_digest_and_never_approves(monkeypatch, tmp_path):
    signed = b"wallet-signed-transaction"
    digest = hashlib.sha256(signed).hexdigest()
    gate_path = tmp_path / "gate.json"
    gate_path.write_text("{}")
    monkeypatch.setattr(workflow, "inspect_fresh_capture", lambda *a, **k: {
        "capture_slot": 100, "slot_age": 1,
    })
    monkeypatch.setattr(workflow, "validate_wallet_signed_claim", lambda *a, **k: {
        "gate_id": "gate", "closure_id": "closure",
        "message_sha256": "a" * 64, "signed_transaction_sha256": digest,
    })
    monkeypatch.setattr(workflow, "read_gate", lambda path: {
        "status": "WALLET_APPROVAL_BOUND", "approval_count": 0,
        "submission_attempt_count": 0, "live_claim_approved": False,
    })
    report = workflow.bind_wallet_signed_evidence(
        gate_path, {}, {}, signed, "wallet", environment=SAFE_ENV,
    )
    assert report["signed_transaction_sha256"] == digest
    assert report["signed_transaction_persisted"] is False
    assert report["approval_count"] == report["submission_attempt_count"] == 0
    assert report["live_claim_approved"] is False
    assert report["claim_submitted"] is False


def test_disabled_safety_flags_fail_closed(tmp_path):
    for name in ("DEXSATO_JUPITER_FEE_ENABLED",
                 "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED",
                 "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED"):
        env = dict(SAFE_ENV)
        env[name] = "true"
        with pytest.raises(workflow.ClaimV2ArtifactWorkflowRejected):
            workflow.bind_wallet_signed_evidence(
                tmp_path / "gate", {}, {}, b"signed", "wallet", environment=env,
            )


def test_workflow_source_has_no_approval_or_submission_operation():
    source = Path(workflow.__file__).read_text(encoding="utf-8")
    forbidden = ("sendTransaction", "submit_claim", "approve_live_claim",
                 "reserve_submission", "private_key", "secret_key")
    assert all(term not in source for term in forbidden)
