import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from application.jupiter_claim_v2_live_approval import (
    CONFIRMATION, approve_live_claim, audit_gate_consumption,
)
from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, bind_wallet_approval, read_gate, reserve_submission,
    write_gate,
)

NOW=datetime(2026,9,2,12,0,tzinfo=timezone.utc)
DIGEST=hashlib.sha256(b"wallet-signed-claim").hexdigest()


def gate(tmp_path):
    path=tmp_path/"claim-gate.json"
    write_gate(path,{"version":1,"gate_id":"g"*32,"status":"ARMED",
      "expires_at":(NOW+timedelta(minutes=5)).isoformat(),"wallet_review_count":0,
      "submission_attempt_count":0,"signed_transaction_sha256":None,
      "wallet_signature_verified":False,"submission_permitted":False,
      "claim_submitted":False,"live_claim_approved":False,
      "claim_execution_ready":False,"execution_ready":False,
      "fee_receipt_verified":False},exclusive=True)
    bind_wallet_approval(path,"g"*32,DIGEST,current=NOW)
    return path


def env(**changes): return {
    "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED":"true",
    "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED":"false",
    "DEXSATO_JUPITER_FEE_ENABLED":"false",**changes}


def approve(path,**kwargs): return approve_live_claim(path,"g"*32,DIGEST,
    CONFIRMATION,environment=env(),current=NOW,**kwargs)


def test_exact_expiring_live_approval_is_persisted_but_not_submitted(tmp_path):
    path=gate(tmp_path);report=approve(path)
    assert report["status"]=="CLAIM_V2_LIVE_APPROVAL_BOUND"
    assert report["submission_permitted"] is True
    assert report["claim_submitted"] is False
    assert report["execution_ready"] is False
    stored=read_gate(path)
    assert stored["status"]=="LIVE_CLAIM_APPROVED"
    assert stored["approval_count"]==1
    assert stored["approval_expires_at"]==(NOW+timedelta(seconds=90)).isoformat()
    assert "transaction" not in stored


@pytest.mark.parametrize("env_change,confirmation,gate_id,digest,code",[
    ({"DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED":"false"},CONFIRMATION,"g"*32,DIGEST,
     "CLAIM_LIVE_APPROVAL_FEATURE_DISABLED"),
    ({"DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED":"true"},CONFIRMATION,"g"*32,DIGEST,
     "DISABLE_SUBMISSION_DURING_APPROVAL"),
    ({"DEXSATO_JUPITER_FEE_ENABLED":"true"},CONFIRMATION,"g"*32,DIGEST,
     "KEEP_PRODUCTION_FEES_DISABLED"),
    ({},"yes","g"*32,DIGEST,"EXPLICIT_LIVE_CLAIM_CONFIRMATION_REQUIRED"),
    ({},CONFIRMATION,"x"*32,DIGEST,"CLAIM_GATE_ID_MISMATCH"),
    ({},CONFIRMATION,"g"*32,"f"*64,"CLAIM_GATE_SIGNED_TRANSACTION_MISMATCH"),
])
def test_weak_unsafe_or_mismatched_approval_is_rejected(
        tmp_path,env_change,confirmation,gate_id,digest,code):
    path=gate(tmp_path)
    with pytest.raises(ClaimV2GateRejected,match=code):
        approve_live_claim(path,gate_id,digest,confirmation,
            environment=env(**env_change),current=NOW)
    assert read_gate(path).get("approval_count",0)==0


def test_approval_cannot_be_replayed_and_wrong_approval_id_cannot_consume(tmp_path):
    path=gate(tmp_path);report=approve(path)
    with pytest.raises(ClaimV2GateRejected,match="CLAIM_WALLET_APPROVAL_REQUIRED"):
        approve(path)
    with pytest.raises(ClaimV2GateRejected,match="CLAIM_LIVE_APPROVAL_ID_MISMATCH"):
        reserve_submission(path,"g"*32,DIGEST,"x"*32,current=NOW)
    assert read_gate(path)["submission_attempt_count"]==0
    reserve_submission(path,"g"*32,DIGEST,report["approval_id"],current=NOW)
    audit=audit_gate_consumption(path)
    assert audit["approval_consumed"] is True
    assert audit["submission_attempt_count"]==1
    with pytest.raises(ClaimV2GateRejected,match="CLAIM_WALLET_APPROVAL_REQUIRED"):
        reserve_submission(path,"g"*32,DIGEST,report["approval_id"],current=NOW)


def test_expired_approval_never_consumes_attempt(tmp_path):
    path=gate(tmp_path);report=approve(path)
    with pytest.raises(ClaimV2GateRejected,match="CLAIM_LIVE_APPROVAL_EXPIRED_OR_INVALID"):
        reserve_submission(path,"g"*32,DIGEST,report["approval_id"],
                           current=NOW+timedelta(seconds=91))
    assert read_gate(path)["submission_attempt_count"]==0
