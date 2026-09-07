"""Bind an F.6C.6 preparation to one short-lived approval; never submit."""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
from application.jupiter_claim_v2_fresh_approval import bind_and_approve_fresh
from application.jupiter_claim_v2_one_shot_gate import ClaimV2GateRejected,read_gate,require

MAX_JSON_BYTES=131072;MAX_SIGNED_BYTES=16384
PREPARATION_STATUS="CLAIM_V2_FRESH_RECONSTRUCTION_PREPARED_REVIEW_REQUIRED"
JIT_HANDOFF_STATUS="CLAIM_V2_JIT_SIGNING_HANDOFF_READY"
def _read(path):
 try:
  raw=Path(path).read_bytes();require(0<len(raw)<=MAX_JSON_BYTES,"INVALID_JSON_INPUT")
  value=json.loads(raw.decode("utf-8-sig"));require(type(value) is dict,"INVALID_JSON_INPUT");return value
 except ClaimV2GateRejected:raise
 except Exception:raise ClaimV2GateRejected("INVALID_JSON_INPUT") from None

def approve_reconstructed_claim(preparation,gate_path,closure,capture,signed,wallet,
 confirmation,*,environment=None,post=None,current=None,decoder=None,
 approver=bind_and_approve_fresh,gate_reader=read_gate):
 env=os.environ if environment is None else environment
 require(env.get("DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED","false").lower()=="true",
  "CLAIM_LIVE_APPROVAL_FEATURE_DISABLED")
 require(env.get("DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED","false").lower()=="false",
  "KEEP_SUBMISSION_DISABLED_DURING_APPROVAL")
 require(env.get("DEXSATO_JUPITER_FEE_ENABLED","false").lower()=="false",
  "KEEP_PRODUCTION_FEES_DISABLED")
 require(type(signed) is bytes and 0<len(signed)<=MAX_SIGNED_BYTES,"INVALID_SIGNED_TRANSACTION")
 require(type(preparation) is dict and preparation.get("status") in
  (PREPARATION_STATUS,JIT_HANDOFF_STATUS),
  "FRESH_RECONSTRUCTION_PREPARATION_REQUIRED")
 if preparation.get("status")==JIT_HANDOFF_STATUS:
  require(preparation.get("operator_action")=="SIGN_IMMEDIATELY"
   and preparation.get("maximum_capture_slot_age")==32
   and type(preparation.get("handoff_slot_age")) is int
   and 0<=preparation.get("handoff_slot_age")<=4
   and type(preparation.get("remaining_slot_budget")) is int
   and preparation.get("remaining_slot_budget")==
    32-preparation.get("handoff_slot_age")
   and preparation.get("gate_consumed") is False
   and preparation.get("submission_permitted") is False,
   "JIT_HANDOFF_CONTRACT_INVALID")
 gate=gate_reader(gate_path)
 require(gate.get("status")=="ARMED" and gate.get("gate_id")==preparation.get("fresh_gate_id")
  and gate.get("closure_id")==preparation.get("fresh_simulation_closure_id")
  and gate.get("message_sha256")==preparation.get("fresh_message_sha256")
  and gate.get("unsigned_transaction_sha256")==preparation.get("fresh_unsigned_transaction_sha256")
  and preparation.get("transaction_signed") is False
  and preparation.get("live_claim_approved") is False
  and preparation.get("submission_attempt_count")==0,
  "FRESH_PREPARATION_GATE_BINDING_MISMATCH")
 digest=hashlib.sha256(signed).hexdigest()
 result=approver(gate_path,closure,capture,signed,wallet,confirmation,
  environment=env,post=post,current=current,decoder=decoder)
 approved=gate_reader(gate_path)
 require(result.get("status")=="FRESH_CLAIM_V2_WALLET_APPROVAL_BOUND"
  and approved.get("status")=="LIVE_CLAIM_APPROVED"
  and approved.get("signed_transaction_sha256")==digest
  and approved.get("approved_signed_transaction_sha256")==digest
  and approved.get("approval_count")==1 and approved.get("wallet_review_count")==1
  and approved.get("submission_attempt_count")==0
  and approved.get("submission_permitted") is True
  and approved.get("claim_submitted") is False,"SHORT_LIVED_APPROVAL_STATE_INVALID")
 return {**result,"status":"CLAIM_V2_SHORT_LIVED_APPROVAL_REVIEW_REQUIRED",
  "signed_transaction_sha256":digest,"pre_submission_inspection_required":True,
  "submission_attempt_count":0,"transaction_submitted":False,"claim_submitted":False,
  "execution_ready":False}

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__)
 for name in ("preparation","gate","closure","capture","signed-transaction-file","wallet","confirm"):
  p.add_argument("--"+name,required=True)
 a=p.parse_args(argv)
 try:
  report=approve_reconstructed_claim(_read(a.preparation),a.gate,_read(a.closure),
   _read(a.capture),Path(a.signed_transaction_file).read_bytes(),a.wallet,a.confirm)
  print(json.dumps(report,separators=(",",":")));return 2
 except ClaimV2GateRejected as e:reason=str(e)
 except Exception:reason="SHORT_LIVED_APPROVAL_INPUT_OR_RPC_UNAVAILABLE"
 print(json.dumps({"status":"CLAIM_V2_SHORT_LIVED_APPROVAL_NOT_VERIFIED","reason":reason,
  "submission_attempt_count":0,"transaction_submitted":False,"claim_submitted":False,
  "execution_ready":False},separators=(",",":")));return 1
if __name__=="__main__":raise SystemExit(main())
