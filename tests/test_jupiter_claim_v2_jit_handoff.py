from pathlib import Path

import pytest

from application import jupiter_claim_v2_jit_handoff as jit
from application.jupiter_claim_v2_fresh_reconstruction import (
    ClaimV2FreshReconstructionRejected,
)


def env(**changes):
    return {
        "DEXSATO_JUPITER_CLAIM_GATE_ENABLED": "true",
        "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED": "false",
        "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED": "false",
        "DEXSATO_JUPITER_FEE_ENABLED": "false",
        "SOLANA_RPC_URL": "https://rpc.example/key",
        **changes,
    }


def prepared():
    return {
        "status": "CLAIM_V2_FRESH_RECONSTRUCTION_PREPARED_REVIEW_REQUIRED",
        "transaction_signed": False,
        "execution_ready": False,
    }


def test_jit_handoff_preserves_32_slot_limit_and_never_approves(monkeypatch,
                                                                tmp_path):
    output = tmp_path / "capture"
    output.mkdir()
    (output / "unsigned_claim_v2_capture.json").write_text("{}")
    (output / "claim_v2_simulation_closure.json").write_text("{}")
    monkeypatch.setattr(jit, "prepare_fresh_reconstruction",
                        lambda *a, **k: prepared())
    monkeypatch.setattr(jit, "_read_json", lambda path: {"rpc_slot":100})
    monkeypatch.setattr(jit, "attest_blockhash", lambda *a, **k: {
        "status":"CLAIM_V2_POST_SIMULATION_BLOCKHASH_ATTESTED",
        "attestation_slot":102,"maximum_attestation_slot_age":32})
    monkeypatch.setattr(jit, "read_gate", lambda path: {
        "status": "ARMED", "approval_count": 0,
        "submission_attempt_count": 0})
    report = jit.prepare_jit_handoff({}, {}, {}, output, tmp_path / "gate",
        "gate-confirm", jit.HANDOFF_CONFIRMATION, environment=env())
    assert report["status"] == "CLAIM_V2_JIT_SIGNING_HANDOFF_READY"
    assert report["maximum_capture_slot_age"] == 32
    assert report["remaining_slot_budget"] == 32
    assert report["live_claim_approved"] is False
    assert report["submission_attempt_count"] == 0
    assert report["transaction_submitted"] is False


@pytest.mark.parametrize("changes,reason", [
    ({"DEXSATO_JUPITER_CLAIM_GATE_ENABLED": "false"},
     "CLAIM_GATE_FEATURE_REQUIRED"),
    ({"DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED": "true"},
     "KEEP_LIVE_APPROVAL_DISABLED"),
    ({"DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED": "true"},
     "KEEP_SUBMISSION_DISABLED"),
    ({"DEXSATO_JUPITER_FEE_ENABLED": "true"},
     "KEEP_PRODUCTION_FEES_DISABLED"),
])
def test_unsafe_flags_stop_before_generation(monkeypatch, tmp_path,
                                              changes, reason):
    called = []
    monkeypatch.setattr(jit, "prepare_fresh_reconstruction",
                        lambda *a, **k: called.append(True))
    with pytest.raises(ClaimV2FreshReconstructionRejected, match=reason):
        jit.prepare_jit_handoff({}, {}, {}, tmp_path / "capture",
            tmp_path / "gate", "gate-confirm", jit.HANDOFF_CONFIRMATION,
            environment=env(**changes))
    assert called == []


def test_explicit_sign_now_phrase_required_before_generation(monkeypatch,
                                                              tmp_path):
    called = []
    monkeypatch.setattr(jit, "prepare_fresh_reconstruction",
                        lambda *a, **k: called.append(True))
    with pytest.raises(ClaimV2FreshReconstructionRejected,
                       match="EXPLICIT_SIGN_NOW_HANDOFF_REQUIRED"):
        jit.prepare_jit_handoff({}, {}, {}, tmp_path / "capture",
            tmp_path / "gate", "gate-confirm", "wrong", environment=env())
    assert called == []


def test_invalid_post_simulation_blockhash_retires_gate(monkeypatch,tmp_path):
    output = tmp_path / "capture"
    output.mkdir()
    monkeypatch.setattr(jit, "prepare_fresh_reconstruction",
                        lambda *a, **k: prepared())
    monkeypatch.setattr(jit, "_read_json", lambda path: {"rpc_slot":100})
    monkeypatch.setattr(jit, "attest_blockhash",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    stale = {"status": "ARMED", "approval_count": 0,
             "submission_attempt_count": 0}
    written = []
    monkeypatch.setattr(jit, "read_gate", lambda path: stale)
    monkeypatch.setattr(jit, "write_gate",
                        lambda path, value: written.append(dict(value)))
    with pytest.raises(ClaimV2FreshReconstructionRejected,
                       match="POST_SIMULATION_BLOCKHASH_NOT_ATTESTED"):
        jit.prepare_jit_handoff({}, {}, {}, output, tmp_path / "gate",
            "gate-confirm", jit.HANDOFF_CONFIRMATION, environment=env())
    assert written[0]["status"] == "JIT_HANDOFF_RETIRED"
    assert written[0]["submission_permitted"] is False
    assert written[0]["execution_ready"] is False


def test_module_has_no_submission_operation():
    source = Path(jit.__file__).read_text(encoding="utf-8")
    assert "sendTransaction" not in source
    assert "submit_claim" not in source
    assert "jupiter_claim_v2_submission" not in source
