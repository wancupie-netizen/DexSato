import base64
import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from application.jupiter_claim_v2_controlled_execution import (
    CONFIRMATION, execute_controlled_claim, inspect_execution_boundary,
)
from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, read_gate, write_gate,
)
from application.jupiter_referral_verification import MAINNET_GENESIS

NOW=datetime(2026,9,2,13,0,tzinfo=timezone.utc)
RAW=b"wallet-signed-funded-claim-v2"
SIGNED=base64.b64encode(RAW).decode()
DIGEST=hashlib.sha256(RAW).hexdigest()
APPROVAL="a"*32


class Response:
    status_code=200
    def __init__(self,payload):self.payload=payload
    def json(self):return self.payload
    def close(self):pass


def gate(tmp_path,**changes):
    path=tmp_path/"claim-gate.json"
    value={"version":1,"gate_id":"g"*32,"status":"LIVE_CLAIM_APPROVED",
      "expires_at":(NOW+timedelta(minutes=3)).isoformat(),
      "approval_expires_at":(NOW+timedelta(seconds=90)).isoformat(),
      "approval_id":APPROVAL,"approval_count":1,"wallet_review_count":1,
      "submission_attempt_count":0,"signed_transaction_sha256":DIGEST,
      "approved_signed_transaction_sha256":DIGEST,"wallet_signature_verified":True,
      "submission_permitted":True,"claim_submitted":False,"live_claim_approved":True,
      "claim_execution_ready":False,"execution_ready":False,"fee_receipt_verified":False,
      "exact_claim_raw":"5000","maximum_claim_raw":"5000",
      "expected_partner_raw":"4000","expected_project_raw":"1000"}
    value.update(changes);write_gate(path,value,exclusive=True);return path


def env(**changes):return {"DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED":"false",
  "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED":"true",
  "DEXSATO_JUPITER_FEE_ENABLED":"false",
  "SOLANA_RPC_URL":"https://rpc.example/key",**changes}


def provider(*,genesis=MAINNET_GENESIS):
    calls=[]
    def post(url,**kwargs):
        calls.append(kwargs["json"]["method"])
        if kwargs["json"]["method"]=="getGenesisHash":
            return Response({"jsonrpc":"2.0","id":1,"result":genesis})
        return Response({"jsonrpc":"2.0","id":1,"result":"s"*88})
    return calls,post


def test_boundary_binds_exact_funded_amounts_and_never_marks_execution_ready(tmp_path):
    report=inspect_execution_boundary(gate(tmp_path),SIGNED,APPROVAL,
                                      environment=env(),current=NOW)
    assert report["exact_claim_raw"]=="5000"
    assert report["expected_partner_raw"]=="4000"
    assert report["expected_project_raw"]=="1000"
    assert report["execution_ready"] is False


@pytest.mark.parametrize("changes,code",[
    ({"exact_claim_raw":"5001"},"CONTROLLED_CLAIM_AMOUNT_CONTRACT_MISMATCH"),
    ({"approved_signed_transaction_sha256":"f"*64},"CLAIM_APPROVED_TRANSACTION_HASH_MISMATCH"),
    ({"submission_attempt_count":1},"CLAIM_GATE_ALREADY_USED_OR_UNSAFE"),
])
def test_amount_hash_or_consumption_tampering_fails_closed(tmp_path,changes,code):
    with pytest.raises(ClaimV2GateRejected,match=code):
        inspect_execution_boundary(gate(tmp_path,**changes),SIGNED,APPROVAL,
                                    environment=env(),current=NOW)


def test_wrong_network_is_rejected_before_gate_consumption(tmp_path):
    path=gate(tmp_path);calls,post=provider(genesis="devnet")
    with pytest.raises(ClaimV2GateRejected,match="SOLANA_MAINNET_GENESIS_MISMATCH"):
        execute_controlled_claim(path,SIGNED,APPROVAL,CONFIRMATION,
                                 environment=env(),post=post,current=NOW)
    assert calls==["getGenesisHash"]
    assert read_gate(path)["submission_attempt_count"]==0


def test_exact_mainnet_submission_consumes_once_without_retry(tmp_path):
    path=gate(tmp_path);calls,post=provider()
    report=execute_controlled_claim(path,SIGNED,APPROVAL,CONFIRMATION,
                                    environment=env(),post=post,current=NOW)
    assert report["status"]=="CONTROLLED_CLAIM_V2_FINALIZATION_PENDING"
    assert report["mainnet_genesis_verified"] is True
    assert report["automatic_retry"] is False
    assert report["execution_ready"] is False
    assert calls==["getGenesisHash","sendTransaction"]
    stored=read_gate(path)
    assert stored["status"]=="FINALIZATION_PENDING"
    assert stored["submission_attempt_count"]==1
    with pytest.raises(ClaimV2GateRejected,match="LIVE_CLAIM_APPROVAL_REQUIRED"):
        execute_controlled_claim(path,SIGNED,APPROVAL,CONFIRMATION,
                                 environment=env(),post=post,current=NOW)
    assert calls==["getGenesisHash","sendTransaction"]


def test_confirmation_and_mutually_exclusive_flags_fail_before_rpc(tmp_path):
    path=gate(tmp_path);calls,post=provider()
    with pytest.raises(ClaimV2GateRejected,match="EXPLICIT_CONTROLLED_CLAIM_CONFIRMATION_REQUIRED"):
        execute_controlled_claim(path,SIGNED,APPROVAL,"yes",environment=env(),post=post,current=NOW)
    with pytest.raises(ClaimV2GateRejected,match="DISABLE_APPROVAL_DURING_SUBMISSION"):
        execute_controlled_claim(path,SIGNED,APPROVAL,CONFIRMATION,
            environment=env(DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED="true"),post=post,current=NOW)
    assert calls==[] and read_gate(path)["submission_attempt_count"]==0
