from datetime import datetime,timezone
import pytest
from application import jupiter_claim_v2_blockhash_attestation as block
from application.jupiter_claim_v2_one_shot_gate import ClaimV2GateRejected

ENV={"DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED":"false",
 "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED":"false",
 "DEXSATO_JUPITER_FEE_ENABLED":"false","SOLANA_RPC_URL":"https://rpc.example/key"}
GATE={"status":"ARMED","gate_id":"gate","closure_id":"closure",
 "message_sha256":"a"*64,"unsigned_transaction_sha256":"b"*64,
 "approval_count":0,"submission_attempt_count":0}
CLOSURE={"status":"FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED","closure_id":"closure",
 "message_sha256":"a"*64,"transaction_sha256":"b"*64}
CAPTURE={"transaction":"encoded","message_sha256":"a"*64,
 "transaction_sha256":"b"*64}
class Response:
 status_code=200
 def __init__(self,result):self.result=result
 def json(self):return {"jsonrpc":"2.0","id":1,"result":self.result}
 def close(self):pass
def provider(valid=True,slot=900):
 calls=[]
 def post(url,**kwargs):
  method=kwargs["json"]["method"];calls.append(method)
  return Response(block.MAINNET_GENESIS if method=="getGenesisHash" else
   {"context":{"slot":slot},"value":valid})
 return calls,post
def test_exact_bytes_blockhash_and_mainnet_are_attested(monkeypatch):
 monkeypatch.setattr(block,"read_gate",lambda path:GATE)
 monkeypatch.setattr(block,"_transaction",lambda capture:(b"raw",b"message","hash"))
 closure={**CLOSURE,"message_sha256":__import__('hashlib').sha256(b"message").hexdigest(),
  "transaction_sha256":__import__('hashlib').sha256(b"raw").hexdigest()}
 gate={**GATE,"message_sha256":closure["message_sha256"],
  "unsigned_transaction_sha256":closure["transaction_sha256"]}
 monkeypatch.setattr(block,"read_gate",lambda path:gate);calls,post=provider()
 report=block.attest_blockhash("gate",closure,CAPTURE,environment=ENV,post=post,
  current=datetime(2026,9,7,tzinfo=timezone.utc))
 assert report["blockhash_valid"] is True and report["attestation_slot"]==900
 assert report["maximum_attestation_slot_age"]==32
 assert calls==["getGenesisHash","isBlockhashValid"]
 assert report["transaction_submitted"] is False
def test_invalid_blockhash_fails_closed(monkeypatch):
 monkeypatch.setattr(block,"read_gate",lambda path:GATE)
 monkeypatch.setattr(block,"_transaction",lambda capture:(b"raw",b"message","hash"))
 closure={**CLOSURE,"message_sha256":__import__('hashlib').sha256(b"message").hexdigest(),
  "transaction_sha256":__import__('hashlib').sha256(b"raw").hexdigest()}
 gate={**GATE,"message_sha256":closure["message_sha256"],
  "unsigned_transaction_sha256":closure["transaction_sha256"]}
 monkeypatch.setattr(block,"read_gate",lambda path:gate);_,post=provider(False)
 with pytest.raises(ClaimV2GateRejected,match="RECENT_BLOCKHASH_NOT_VALID"):
  block.attest_blockhash("gate",closure,CAPTURE,environment=ENV,post=post)
def test_module_has_no_submission_operation():
 source=open(block.__file__,encoding="utf-8").read()
 assert "sendTransaction" not in source and "submit_claim" not in source
