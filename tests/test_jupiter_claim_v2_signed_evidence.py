import hashlib
from pathlib import Path

import pytest

from application import jupiter_claim_v2_signed_evidence as evidence


def transaction(message=b"versioned-message", signatures=1):
    return bytes([signatures]) + (b"S" * 64 * signatures) + message


def test_independent_wire_hashes_are_exact():
    raw = transaction()
    report = evidence.independent_transaction_hashes(raw)
    assert report["signed_transaction_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["message_sha256"] == hashlib.sha256(b"versioned-message").hexdigest()
    assert report["signature_count"] == 1
    assert report["message_offset"] == 65


@pytest.mark.parametrize("raw,reason", [
    (b"", "INVALID_SIGNED_TRANSACTION_SIZE"),
    (b"\x00message", "INVALID_SIGNATURE_COUNT"),
    (b"\x01" + b"S" * 64, "TRUNCATED_SIGNED_TRANSACTION"),
    (b"\x81\x00" + b"S" * 64 + b"m", "NON_CANONICAL_SIGNATURE_COUNT"),
])
def test_malformed_wire_input_rejected(raw, reason):
    with pytest.raises(evidence.ClaimV2SignedEvidenceRejected, match=reason):
        evidence.independent_transaction_hashes(raw)


def test_capture_cross_checks_then_persists_hash_only(tmp_path):
    raw = transaction()
    message_hash = hashlib.sha256(b"versioned-message").hexdigest()
    signed_hash = hashlib.sha256(raw).hexdigest()
    capture = {"status": "SDK_UNSIGNED_CAPTURED", "message_sha256": message_hash}
    calls = []

    def binder(gate, closure, capture_value, signed, wallet, **kwargs):
        calls.append((gate, signed, wallet))
        return {"gate_id": "gate", "closure_id": "closure",
                "message_sha256": message_hash,
                "signed_transaction_sha256": signed_hash}

    output = tmp_path / "signed_hash_evidence.json"
    report = evidence.capture_wallet_signed_evidence(
        tmp_path / "gate.json", {}, capture, raw, "wallet", output,
        environment={}, binder=binder,
    )
    assert calls == [(tmp_path / "gate.json", raw, "wallet")]
    assert report["status"] == "CLAIM_V2_WALLET_SIGNED_HASH_INDEPENDENTLY_VERIFIED"
    assert report["approval_count"] == report["submission_attempt_count"] == 0
    assert report["live_claim_approved"] is False
    persisted = output.read_bytes()
    assert raw not in persisted
    assert b"SSSSSSSS" not in persisted
    assert signed_hash.encode() in persisted


def test_message_mismatch_stops_before_gate_binding(tmp_path):
    with pytest.raises(evidence.ClaimV2SignedEvidenceRejected,
                       match="INDEPENDENT_MESSAGE_HASH_MISMATCH"):
        evidence.capture_wallet_signed_evidence(
            tmp_path / "gate", {},
            {"status": "SDK_UNSIGNED_CAPTURED", "message_sha256": "0" * 64},
            transaction(), "wallet", tmp_path / "report.json",
            binder=lambda *a, **k: pytest.fail("gate must remain untouched"),
        )


def test_existing_report_stops_before_gate_binding(tmp_path):
    output = tmp_path / "report.json"
    output.write_text("{}")
    with pytest.raises(evidence.ClaimV2SignedEvidenceRejected,
                       match="EVIDENCE_OUTPUT_ALREADY_EXISTS"):
        evidence.capture_wallet_signed_evidence(
            tmp_path / "gate", {}, {}, transaction(), "wallet", output,
            binder=lambda *a, **k: pytest.fail("gate must remain untouched"),
        )


def test_source_contains_no_approval_submission_or_secret_handling():
    source = Path(evidence.__file__).read_text(encoding="utf-8")
    forbidden = ("sendTransaction", "submit_claim", "approve_live_claim",
                 "reserve_submission", "private_key", "secret_key")
    assert all(term not in source for term in forbidden)


def test_no_submission_binding_uses_gate_ttl_without_rpc_slot_claim(monkeypatch):
    expected = {"gate_id": "gate", "closure_id": "closure",
                "message_sha256": "a" * 64,
                "signed_transaction_sha256": "b" * 64}
    seen = []
    monkeypatch.setattr(evidence, "validate_wallet_signed_claim",
                        lambda *args, **kwargs: seen.append((args, kwargs)) or expected)
    monkeypatch.setattr(evidence, "read_gate", lambda path: {
        "status": "WALLET_APPROVAL_BOUND", "approval_count": 0,
        "submission_attempt_count": 0, "live_claim_approved": False,
        "claim_submitted": False, "execution_ready": False,
    })
    result = evidence.bind_no_submission_evidence(
        "gate.json", {}, {}, b"signed", "wallet",
        environment={"DEXSATO_JUPITER_FEE_ENABLED": "false",
                     "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED": "false",
                     "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED": "false"},
    )
    assert result == expected and len(seen) == 1


@pytest.mark.parametrize("flag", [
    "DEXSATO_JUPITER_FEE_ENABLED",
    "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED",
    "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED",
])
def test_no_submission_binding_rejects_every_unsafe_flag(monkeypatch, flag):
    monkeypatch.setattr(evidence, "validate_wallet_signed_claim",
                        lambda *args, **kwargs: pytest.fail("gate must remain untouched"))
    with pytest.raises(evidence.ClaimV2SignedEvidenceRejected):
        evidence.bind_no_submission_evidence(
            "gate.json", {}, {}, b"signed", "wallet", environment={flag: "true"},
        )


def test_evidence_report_requires_live_reconstruction(tmp_path):
    raw = transaction()
    message_hash = hashlib.sha256(b"versioned-message").hexdigest()
    signed_hash = hashlib.sha256(raw).hexdigest()
    report = evidence.capture_wallet_signed_evidence(
        "gate", {}, {"status": "SDK_UNSIGNED_CAPTURED",
                     "message_sha256": message_hash}, raw, "wallet",
        tmp_path / "report.json", binder=lambda *args, **kwargs: {
            "gate_id": "gate", "closure_id": "closure",
            "message_sha256": message_hash,
            "signed_transaction_sha256": signed_hash,
        },
    )
    assert report["capture_freshness_policy"] == "GATE_TTL_ONLY_NO_SUBMISSION"
    assert report["rpc_freshness_verified"] is False
    assert report["live_reconstruction_required"] is True
    assert report["execution_ready"] is False
