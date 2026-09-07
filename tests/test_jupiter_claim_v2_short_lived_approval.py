import hashlib
from datetime import datetime,timezone
import pytest
from application import jupiter_claim_v2_short_lived_approval as short
from application.jupiter_claim_v2_one_shot_gate import ClaimV2GateRejected
RAW=b"signed";DIGEST=hashlib.sha256(RAW).hexdigest();NOW=datetime(2026,9,7,tzinfo=timezone.utc)
ENV={"DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED":"true",
 "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED":"false","DEXSATO_JUPITER_FEE_ENABLED":"false"}
PREP={"status":"CLAIM_V2_FRESH_RECONSTRUCTION_PREPARED_REVIEW_REQUIRED",
 "fresh_gate_id":"gate","fresh_simulation_closure_id":"closure",
 "fresh_message_sha256":"a"*64,"fresh_unsigned_transaction_sha256":"b"*64,
 "transaction_signed":False,"live_claim_approved":False,"submission_attempt_count":0}
JIT={**PREP,"status":"CLAIM_V2_JIT_SIGNING_HANDOFF_READY",
 "operator_action":"SIGN_IMMEDIATELY","maximum_capture_slot_age":32,
 "handoff_slot_age":2,"remaining_slot_budget":30,"gate_consumed":False,
 "submission_permitted":False,"blockhash_attestation":{"status":"attested"}}
ARMED={"status":"ARMED","gate_id":"gate","closure_id":"closure","message_sha256":"a"*64,
 "unsigned_transaction_sha256":"b"*64}
APPROVED={**ARMED,"status":"LIVE_CLAIM_APPROVED","signed_transaction_sha256":DIGEST,
 "approved_signed_transaction_sha256":DIGEST,"approval_count":1,"wallet_review_count":1,
 "submission_attempt_count":0,"submission_permitted":True,"claim_submitted":False}
def test_exact_preparation_reaches_review_only_approval():
 states=iter((ARMED,APPROVED))
 result=short.approve_reconstructed_claim(PREP,"gate",{}, {},RAW,"wallet","confirm",
  environment=ENV,current=NOW,gate_reader=lambda p:next(states),approver=lambda *a,**k:
  {"status":"FRESH_CLAIM_V2_WALLET_APPROVAL_BOUND","approval_id":"id",
   "approval_expires_at":"soon","execution_ready":False})
 assert result["status"]=="CLAIM_V2_SHORT_LIVED_APPROVAL_REVIEW_REQUIRED"
 assert result["pre_submission_inspection_required"] is True
 assert result["submission_attempt_count"]==0 and result["claim_submitted"] is False
@pytest.mark.parametrize("preparation",[PREP,JIT])
def test_legacy_and_exact_jit_contract_reach_same_approval_boundary(preparation):
 states=iter((ARMED,APPROVED))
 result=short.approve_reconstructed_claim(preparation,"gate",{}, {},RAW,"wallet","confirm",
  environment=ENV,current=NOW,gate_reader=lambda p:next(states),
  freshness_attestation=preparation.get("blockhash_attestation"),approver=lambda *a,**k:
  {"status":"FRESH_CLAIM_V2_WALLET_APPROVAL_BOUND","approval_id":"id",
   "approval_expires_at":"soon","execution_ready":False})
 assert result["status"]=="CLAIM_V2_SHORT_LIVED_APPROVAL_REVIEW_REQUIRED"
 assert result["transaction_submitted"] is False
@pytest.mark.parametrize("field,value",[("operator_action","WAIT"),
 ("maximum_capture_slot_age",33),("handoff_slot_age",5),
 ("remaining_slot_budget",29),("gate_consumed",True),
 ("submission_permitted",True)])
def test_malformed_jit_contract_stops_before_gate_read_or_approval(field,value):
 changed={**JIT,field:value};called=[]
 with pytest.raises(ClaimV2GateRejected,match="JIT_HANDOFF_CONTRACT_INVALID"):
  short.approve_reconstructed_claim(changed,"gate",{}, {},RAW,"wallet","confirm",
   environment=ENV,gate_reader=lambda p:called.append("read"),
   approver=lambda *a,**k:called.append("approve"))
 assert called==[]
def test_unrelated_status_is_not_promoted_to_preparation():
 with pytest.raises(ClaimV2GateRejected,
                    match="FRESH_RECONSTRUCTION_PREPARATION_REQUIRED"):
  short.approve_reconstructed_claim({**PREP,"status":"ARMED"},"gate",{}, {},RAW,
   "wallet","confirm",environment=ENV,gate_reader=lambda p:ARMED,
   approver=lambda *a,**k:pytest.fail("must not approve"))
@pytest.mark.parametrize("field,value",[("fresh_gate_id","old"),("transaction_signed",True),
 ("submission_attempt_count",1)])
def test_mismatch_stops_before_approval(field,value):
 changed={**PREP,field:value}
 with pytest.raises(ClaimV2GateRejected,match="FRESH_PREPARATION_GATE_BINDING_MISMATCH"):
  short.approve_reconstructed_claim(changed,"gate",{}, {},RAW,"wallet","confirm",
   environment=ENV,gate_reader=lambda p:ARMED,
   approver=lambda *a,**k:pytest.fail("must not approve"))
def test_source_contains_no_submission_operation():
 source=open(short.__file__,encoding="utf-8").read()
 assert all(x not in source for x in ("submit_claim","sendTransaction","reserve_submission","private_key"))
