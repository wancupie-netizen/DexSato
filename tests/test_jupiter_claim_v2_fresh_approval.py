from pathlib import Path

import pytest

from application import jupiter_claim_v2_fresh_approval as fresh
from application.jupiter_claim_v2_one_shot_gate import ClaimV2GateRejected,read_gate,write_gate
from application.jupiter_referral_verification import MAINNET_GENESIS

CAPTURE_SLOT=443800000

class Response:
 status_code=200
 def __init__(self,value):self.value=value
 def json(self):return self.value
 def close(self):pass

def capture():return {"status":"SDK_UNSIGNED_CAPTURED","sdk_version":"0.3.0",
 "rpc_slot":CAPTURE_SLOT,"message_sha256":"a"*64,"transaction_sha256":"b"*64,
 "transaction":"unsigned","identity":{"payer":"wallet","partner":"wallet"},
 "execution_ready":False,"fee_receipt_verified":False}

def closure():return {"status":"FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED",
 "message_sha256":"a"*64,"transaction_sha256":"b"*64,"gross_claim_raw":"5000",
 "partner_delta_raw":"4000","project_admin_delta_raw":"1000",
 "claim_execution_approved":False,"execution_ready":False}

def gate(tmp_path,**changes):
 path=tmp_path/"gate.json";value={"status":"ARMED","gate_id":"g"*32,
  "message_sha256":"a"*64,"unsigned_transaction_sha256":"b"*64,
  "submission_attempt_count":0,"approval_count":0};value.update(changes)
 write_gate(path,value,exclusive=True);return path

def env(**changes):return {"DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED":"true",
 "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED":"false","DEXSATO_JUPITER_FEE_ENABLED":"false",
 "SOLANA_RPC_URL":"https://rpc.example/key",**changes}

def provider(slot=CAPTURE_SLOT+4,genesis=MAINNET_GENESIS):
 calls=[]
 def post(url,**kwargs):
  method=kwargs["json"]["method"];calls.append(method)
  return Response({"jsonrpc":"2.0","id":1,
    "result":genesis if method=="getGenesisHash" else slot})
 return calls,post

def test_fresh_capture_gate_and_closure_are_bound_without_mutation(tmp_path):
 path=gate(tmp_path);before=path.read_bytes();calls,post=provider()
 report=fresh.inspect_fresh_capture(path,closure(),capture(),environment=env(),post=post)
 assert report["slot_age"]==4 and report["mainnet_genesis_verified"] is True
 assert report["transaction_signed"] is False and report["execution_ready"] is False
 assert calls==["getGenesisHash","getSlot"] and path.read_bytes()==before

@pytest.mark.parametrize("slot,code",[
 (CAPTURE_SLOT-1,"FRESH_CAPTURE_SLOT_WINDOW_EXCEEDED"),
 (CAPTURE_SLOT+33,"FRESH_CAPTURE_SLOT_WINDOW_EXCEEDED")])
def test_future_or_stale_capture_slot_is_rejected(tmp_path,slot,code):
 calls,post=provider(slot=slot)
 with pytest.raises(ClaimV2GateRejected,match=code):
  fresh.inspect_fresh_capture(gate(tmp_path),closure(),capture(),environment=env(),post=post)

def test_wrong_network_stops_before_slot_query(tmp_path):
 calls,post=provider(genesis="devnet")
 with pytest.raises(ClaimV2GateRejected,match="SOLANA_MAINNET_GENESIS_MISMATCH"):
  fresh.inspect_fresh_capture(gate(tmp_path),closure(),capture(),environment=env(),post=post)
 assert calls==["getGenesisHash"]

def test_capture_closure_or_gate_hash_mismatch_stops_before_rpc(tmp_path):
 changed=closure();changed["transaction_sha256"]="c"*64;calls,post=provider()
 with pytest.raises(ClaimV2GateRejected,match="FRESH_CLOSURE_CAPTURE_BINDING_MISMATCH"):
  fresh.inspect_fresh_capture(gate(tmp_path),changed,capture(),environment=env(),post=post)
 second = tmp_path / "second"
 second.mkdir()
 with pytest.raises(ClaimV2GateRejected,match="FRESH_GATE_CAPTURE_BINDING_MISMATCH"):
  fresh.inspect_fresh_capture(gate(second,message_sha256="d"*64),closure(),capture(),environment=env(),post=post)
 assert calls==[]

def test_coordinator_binds_wallet_then_approves_but_never_submits(monkeypatch,tmp_path):
 path=gate(tmp_path);calls,post=provider();order=[]
 monkeypatch.setattr(fresh,"validate_wallet_signed_claim",lambda *a,**k:
  order.append("wallet") or {"gate_id":"g"*32,"signed_transaction_sha256":"s"*64})
 monkeypatch.setattr(fresh,"approve_live_claim",lambda *a,**k:
  order.append("approval") or {"approval_id":"p"*32,"approval_expires_at":"soon"})
 report=fresh.bind_and_approve_fresh(path,closure(),capture(),"signed","wallet",
  fresh.CONFIRMATION,environment=env(),post=post)
 assert order==["wallet","approval"]
 assert report["status"]=="FRESH_CLAIM_V2_WALLET_APPROVAL_BOUND"
 assert report["transaction_submitted"] is False and report["execution_ready"] is False
 assert read_gate(path)["submission_attempt_count"]==0

def test_module_contains_no_submission_provider_method():
 source=Path(fresh.__file__).read_text(encoding="utf-8")
 assert "sendTransaction" not in source and "submit_claim" not in source
