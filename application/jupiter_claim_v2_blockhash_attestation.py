"""Attest an exact ClaimV2 transaction blockhash after funded simulation."""
from __future__ import annotations
import base64,hashlib,json,os
from datetime import timezone
from pathlib import Path
from urllib.parse import urlparse
from application.jupiter_claim_v2_one_shot_gate import (
 ClaimV2GateRejected,read_gate,require,utc_now)
from application.jupiter_claim_v2_wallet_boundary import _versioned_message_bytes
from application.jupiter_referral_verification import MAINNET_GENESIS

MAX_ATTESTATION_SLOT_AGE=32
def _endpoint(value):
 require(type(value) is str and 1<=len(value)<=2048,"HTTPS_RPC_CONFIGURATION_REQUIRED")
 parsed=urlparse(value);require(parsed.scheme=="https" and bool(parsed.netloc)
  and parsed.username is None and parsed.password is None
  and not parsed.fragment,"HTTPS_RPC_CONFIGURATION_REQUIRED")
 return value
def _rpc(post,endpoint,method,params):
 response=None
 try:
  if post is None:
   import requests;post=requests.post
  response=post(endpoint,json={"jsonrpc":"2.0","id":1,"method":method,
   "params":params},timeout=(3,20),allow_redirects=False)
  require(response.status_code==200,"RPC_HTTP_ERROR")
  payload=response.json();require(type(payload) is dict and payload.get("jsonrpc")=="2.0"
   and payload.get("id")==1 and payload.get("error") is None,"INVALID_RPC_RESPONSE")
  return payload.get("result")
 finally:
  if response is not None:response.close()
def _transaction(capture):
 require(type(capture) is dict and type(capture.get("transaction")) is str,
  "FRESH_UNSIGNED_CAPTURE_REQUIRED")
 try:
  raw=base64.b64decode(capture["transaction"],validate=True)
  from solders.transaction import VersionedTransaction
  transaction=VersionedTransaction.from_bytes(raw)
  message=_versioned_message_bytes(transaction.message)
 except ClaimV2GateRejected:raise
 except Exception:raise ClaimV2GateRejected("INVALID_VERSIONED_TRANSACTION") from None
 require(hashlib.sha256(raw).hexdigest()==capture.get("transaction_sha256")
  and hashlib.sha256(message).hexdigest()==capture.get("message_sha256"),
  "CAPTURE_BYTE_HASH_MISMATCH")
 return raw,message,str(transaction.message.recent_blockhash)
def attest_blockhash(gate_path,closure,capture,*,environment=None,post=None,current=None,
                     allow_live_approval=False):
 env=os.environ if environment is None else environment
 require((allow_live_approval or
  env.get("DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED","false").lower()=="false")
  and env.get("DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED","false").lower()=="false"
  and env.get("DEXSATO_JUPITER_FEE_ENABLED","false").lower()=="false",
  "KEEP_EXECUTION_DISABLED_DURING_ATTESTATION")
 gate=read_gate(gate_path);require(gate.get("status")=="ARMED"
  and gate.get("approval_count")==0 and gate.get("submission_attempt_count")==0,
  "FRESH_GATE_REQUIRED")
 raw,message,blockhash=_transaction(capture)
 require(type(closure) is dict and closure.get("status")==
  "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED"
  and closure.get("closure_id")==gate.get("closure_id")
  and closure.get("message_sha256")==hashlib.sha256(message).hexdigest()
  and closure.get("transaction_sha256")==hashlib.sha256(raw).hexdigest()
  and gate.get("message_sha256")==closure.get("message_sha256")
  and gate.get("unsigned_transaction_sha256")==closure.get("transaction_sha256"),
  "BLOCKHASH_ATTESTATION_BINDING_MISMATCH")
 endpoint=_endpoint(env.get("SOLANA_RPC_URL",""))
 require(_rpc(post,endpoint,"getGenesisHash",[])==MAINNET_GENESIS,
  "SOLANA_MAINNET_GENESIS_MISMATCH")
 result=_rpc(post,endpoint,"isBlockhashValid",[blockhash,{"commitment":"finalized"}])
 require(type(result) is dict and type(result.get("context")) is dict
  and type(result["context"].get("slot")) is int and result.get("value") is True,
  "RECENT_BLOCKHASH_NOT_VALID")
 now=current or utc_now();require(now.tzinfo is not None,"INVALID_ATTESTATION_TIMESTAMP")
 return {"status":"CLAIM_V2_POST_SIMULATION_BLOCKHASH_ATTESTED",
  "gate_id":gate["gate_id"],"closure_id":closure["closure_id"],
  "message_sha256":closure["message_sha256"],
  "transaction_sha256":closure["transaction_sha256"],"recent_blockhash":blockhash,
  "attestation_slot":result["context"]["slot"],
  "attested_at":now.astimezone(timezone.utc).isoformat(),
  "maximum_attestation_slot_age":MAX_ATTESTATION_SLOT_AGE,
  "blockhash_valid":True,"gate_consumed":False,"live_claim_approved":False,
  "submission_attempt_count":0,"transaction_submitted":False,
  "claim_submitted":False,"execution_ready":False}
def verify_blockhash_attestation(gate_path,closure,capture,attestation,*,environment=None,post=None):
 current=attest_blockhash(gate_path,closure,capture,environment=environment,post=post,
  allow_live_approval=True)
 expected={k:v for k,v in current.items() if k not in ("attestation_slot","attested_at")}
 require(type(attestation) is dict and all(attestation.get(k)==v for k,v in expected.items()),
  "BLOCKHASH_ATTESTATION_MISMATCH")
 age=current["attestation_slot"]-attestation.get("attestation_slot",-1)
 require(type(attestation.get("attestation_slot")) is int and 0<=age<=MAX_ATTESTATION_SLOT_AGE,
  "BLOCKHASH_ATTESTATION_SLOT_WINDOW_EXCEEDED")
 return {**current,"source_attestation_slot":attestation["attestation_slot"],
  "attestation_slot_age":age}
