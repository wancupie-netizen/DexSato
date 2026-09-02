"""Disabled-by-default, one-attempt ClaimV2 RPC submission harness."""
from __future__ import annotations
import base64,hashlib,json,os
from urllib.parse import urlsplit
from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected,read_gate,record_submission_result,require,reserve_submission,
)

FLAG="DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED"
CONFIRMATION="I APPROVE ONE CLAIM V2 SUBMISSION"
MAX_BYTES=4096

def _endpoint(value):
    try:
        parsed=urlsplit(value);require(parsed.scheme=="https" and parsed.hostname
            and not parsed.username and not parsed.password and not parsed.fragment,
            "HTTPS_RPC_CONFIGURATION_REQUIRED")
    except (TypeError,ValueError):
        raise ClaimV2GateRejected("HTTPS_RPC_CONFIGURATION_REQUIRED") from None
    return value

def _signed(value):
    require(type(value) is str and len(value)<=8192,"INVALID_SIGNED_TRANSACTION")
    try:raw=base64.b64decode(value,validate=True)
    except Exception:raise ClaimV2GateRejected("INVALID_SIGNED_TRANSACTION") from None
    require(1<=len(raw)<=MAX_BYTES,"INVALID_SIGNED_TRANSACTION")
    return raw

def submit_claim(path,signed_transaction,confirmation,*,environment=None,post=None,current=None):
    env=os.environ if environment is None else environment
    require(env.get(FLAG,"false").strip().lower()=="true",
            "CLAIM_SUBMISSION_FEATURE_DISABLED")
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED","false").strip().lower()=="false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    require(confirmation==CONFIRMATION,"EXPLICIT_SUBMISSION_CONFIRMATION_REQUIRED")
    raw=_signed(signed_transaction);digest=hashlib.sha256(raw).hexdigest()
    endpoint=_endpoint(env.get("SOLANA_RPC_URL",""))
    gate=read_gate(path)
    reserve_submission(path,gate.get("gate_id"),digest,current=current)
    payload={"jsonrpc":"2.0","id":1,"method":"sendTransaction","params":[
        signed_transaction,{"encoding":"base64","skipPreflight":False,
        "preflightCommitment":"confirmed","maxRetries":0}]}
    response=None
    try:
        if post is None:
            import requests
            post=requests.post
        response=post(endpoint,json=payload,timeout=(3,20),
            allow_redirects=False)
        if response.status_code!=200:
            record_submission_result(path,gate["gate_id"],failure_reason="RPC_HTTP_ERROR")
            raise ClaimV2GateRejected("RPC_HTTP_ERROR")
        result=response.json()
        if type(result) is not dict or result.get("jsonrpc")!="2.0" or result.get("id")!=1:
            record_submission_result(path,gate["gate_id"],failure_reason="INVALID_RPC_RESPONSE")
            raise ClaimV2GateRejected("INVALID_RPC_RESPONSE")
        if result.get("error") is not None:
            record_submission_result(path,gate["gate_id"],failure_reason="RPC_REJECTED")
            raise ClaimV2GateRejected("RPC_REJECTED")
        signature=result.get("result")
        if type(signature) is not str or not 64<=len(signature)<=96:
            record_submission_result(path,gate["gate_id"],failure_reason="INVALID_RPC_RESPONSE")
            raise ClaimV2GateRejected("INVALID_RPC_RESPONSE")
        updated=record_submission_result(path,gate["gate_id"],signature=signature)
        return {"status":"CLAIM_V2_FINALIZATION_PENDING","signature":updated["signature"],
            "submission_attempt_count":1,"claim_submitted":True,
            "claim_receipt_verified":False,"execution_ready":False}
    except ClaimV2GateRejected:raise
    except Exception:
        record_submission_result(path,gate["gate_id"],failure_reason="RPC_UNAVAILABLE")
        raise ClaimV2GateRejected("RPC_UNAVAILABLE") from None
    finally:
        if response is not None:response.close()
