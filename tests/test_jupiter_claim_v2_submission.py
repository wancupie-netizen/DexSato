import base64
import hashlib
from datetime import datetime, timezone

import pytest

from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, bind_wallet_approval, read_gate, write_gate,
)
from application.jupiter_claim_v2_submission import CONFIRMATION, submit_claim

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
RAW = b"wallet-signed-claim-v2"
ENCODED = base64.b64encode(RAW).decode()
DIGEST = hashlib.sha256(RAW).hexdigest()


class Response:
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def json(self): return self.payload
    def close(self): pass


def bound_gate(tmp_path, *, approved=False):
    path = tmp_path / "gate.json"
    write_gate(path, {"version": 1, "gate_id": "g" * 32, "status": "ARMED",
        "expires_at": "2026-09-02T12:05:00+00:00", "wallet_review_count": 0,
        "submission_attempt_count": 0, "signed_transaction_sha256": None,
        "wallet_signature_verified": False, "submission_permitted": False,
        "claim_submitted": False, "live_claim_approved": False,
        "claim_execution_ready": False, "execution_ready": False,
        "fee_receipt_verified": False}, exclusive=True)
    bind_wallet_approval(path, "g" * 32, DIGEST, current=NOW)
    if approved:
        gate = read_gate(path)
        gate.update(status="LIVE_CLAIM_APPROVED", submission_permitted=True,
            live_claim_approved=True, approval_id="a"*32, approval_count=1,
            approved_signed_transaction_sha256=DIGEST,
            approval_expires_at="2026-09-02T12:01:30+00:00")
        write_gate(path, gate)
    return path


def env(**changes):
    return {"DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED": "true",
        "DEXSATO_JUPITER_FEE_ENABLED": "false",
        "SOLANA_RPC_URL": "https://rpc.example/key", **changes}


def test_f5_gate_cannot_submit_without_later_live_approval(tmp_path):
    called = False
    def post(*args, **kwargs):
        nonlocal called; called = True
    path = bound_gate(tmp_path)
    with pytest.raises(ClaimV2GateRejected, match="LIVE_CLAIM_APPROVAL_REQUIRED"):
        submit_claim(path, ENCODED, CONFIRMATION, environment=env(), post=post,
                     current=NOW)
    assert called is False
    assert read_gate(path)["submission_attempt_count"] == 0


@pytest.mark.parametrize("changes,confirmation,code", [
    ({"DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED": "false"}, CONFIRMATION,
     "CLAIM_SUBMISSION_FEATURE_DISABLED"),
    ({"DEXSATO_JUPITER_FEE_ENABLED": "true"}, CONFIRMATION,
     "KEEP_PRODUCTION_FEES_DISABLED"),
    ({}, "yes", "EXPLICIT_SUBMISSION_CONFIRMATION_REQUIRED"),
    ({"SOLANA_RPC_URL": "http://rpc.example"}, CONFIRMATION,
     "HTTPS_RPC_CONFIGURATION_REQUIRED"),
])
def test_disabled_unsafe_or_weak_configuration_fails_before_attempt(
        tmp_path, changes, confirmation, code):
    path = bound_gate(tmp_path, approved=True)
    with pytest.raises(ClaimV2GateRejected, match=code):
        submit_claim(path, ENCODED, confirmation, "a"*32, environment=env(**changes),
                     post=lambda *a, **k: None, current=NOW)
    assert read_gate(path)["submission_attempt_count"] == 0


def test_approved_mock_submission_consumes_exactly_one_attempt(tmp_path):
    path = bound_gate(tmp_path, approved=True)
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response({"jsonrpc": "2.0", "id": 1, "result": "s" * 88})
    report = submit_claim(path, ENCODED, CONFIRMATION, "a"*32, environment=env(),
                          post=post, current=NOW)
    assert report["status"] == "CLAIM_V2_FINALIZATION_PENDING"
    assert report["execution_ready"] is False
    assert calls[0][1]["json"]["method"] == "sendTransaction"
    assert calls[0][1]["json"]["params"][1]["maxRetries"] == 0
    stored = read_gate(path)
    assert stored["submission_attempt_count"] == 1
    assert stored["status"] == "FINALIZATION_PENDING"
    with pytest.raises(ClaimV2GateRejected, match="CLAIM_WALLET_APPROVAL_REQUIRED"):
        submit_claim(path, ENCODED, CONFIRMATION, "a"*32, environment=env(), post=post,
                     current=NOW)
    assert len(calls) == 1


def test_rpc_failure_is_safe_and_non_retryable(tmp_path):
    path = bound_gate(tmp_path, approved=True)
    with pytest.raises(ClaimV2GateRejected, match="RPC_REJECTED"):
        submit_claim(path, ENCODED, CONFIRMATION, "a"*32, environment=env(),
            post=lambda *a, **k: Response({"jsonrpc":"2.0","id":1,
                                           "error":{"message":"secret"}}),
            current=NOW)
    gate = read_gate(path)
    assert gate["status"] == "FAILED" and gate["failure_reason"] == "RPC_REJECTED"
    assert "secret" not in str(gate)
