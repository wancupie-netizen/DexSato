"""Fresh ClaimV2 capture, wallet-binding and time-bounded approval coordinator."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from application.jupiter_claim_v2_live_approval import (
    CONFIRMATION, approve_live_claim,
)
from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, read_gate, require, utc_now,
)
from application.jupiter_claim_v2_submission import _endpoint
from application.jupiter_claim_v2_wallet_boundary import validate_wallet_signed_claim
from application.jupiter_referral_verification import MAINNET_GENESIS

MAX_CAPTURE_SLOT_AGE=32
MAX_SIGNED_FILE_BYTES=16_384

def _read_json(path):
    raw=Path(path).read_bytes()
    require(len(raw)<=65_536,"INVALID_JSON_INPUT")
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,"DUPLICATE_JSON_KEY");result[key]=value
        return result
    try:value=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    except ClaimV2GateRejected:raise
    except Exception:raise ClaimV2GateRejected("INVALID_JSON_INPUT") from None
    require(type(value) is dict,"INVALID_JSON_INPUT")
    return value


def _rpc(post,endpoint,method,params):
    response=None
    try:
        if post is None:
            import requests
            post=requests.post
        response=post(endpoint,json={"jsonrpc":"2.0","id":1,"method":method,
            "params":params},timeout=(3,20),allow_redirects=False)
        require(response.status_code==200,"RPC_HTTP_ERROR")
        payload=response.json()
        require(type(payload) is dict and payload.get("jsonrpc")=="2.0"
            and payload.get("id")==1 and payload.get("error") is None,
            "INVALID_RPC_RESPONSE")
        return payload.get("result")
    finally:
        if response is not None:response.close()


def inspect_fresh_capture(path,closure,capture,*,environment=None,post=None):
    env=os.environ if environment is None else environment
    require(env.get("DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED","false")
            .strip().lower()=="false","KEEP_SUBMISSION_DISABLED_DURING_APPROVAL")
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED","false").strip().lower()=="false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    endpoint=_endpoint(env.get("SOLANA_RPC_URL",""))
    require(type(capture) is dict and capture.get("status")=="SDK_UNSIGNED_CAPTURED"
            and capture.get("sdk_version")=="0.3.0"
            and capture.get("execution_ready") is False,
            "FRESH_UNSIGNED_CAPTURE_REQUIRED")
    require(type(closure) is dict
            and closure.get("status")=="FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED"
            and closure.get("message_sha256")==capture.get("message_sha256")
            and closure.get("transaction_sha256")==capture.get("transaction_sha256")
            and closure.get("gross_claim_raw")=="5000"
            and closure.get("partner_delta_raw")=="4000"
            and closure.get("project_admin_delta_raw")=="1000"
            and closure.get("claim_execution_approved") is False,
            "FRESH_CLOSURE_CAPTURE_BINDING_MISMATCH")
    gate=read_gate(path)
    require(gate.get("status")=="ARMED"
            and gate.get("message_sha256")==capture.get("message_sha256")
            and gate.get("unsigned_transaction_sha256")==capture.get("transaction_sha256")
            and gate.get("submission_attempt_count")==0
            and gate.get("approval_count",0)==0,
            "FRESH_GATE_CAPTURE_BINDING_MISMATCH")
    genesis=_rpc(post,endpoint,"getGenesisHash",[])
    require(genesis==MAINNET_GENESIS,"SOLANA_MAINNET_GENESIS_MISMATCH")
    current_slot=_rpc(post,endpoint,"getSlot",[{"commitment":"finalized"}])
    capture_slot=capture.get("rpc_slot")
    require(type(current_slot) is int and type(capture_slot) is int
            and capture_slot>0 and capture_slot<=current_slot
            and current_slot-capture_slot<=MAX_CAPTURE_SLOT_AGE,
            "FRESH_CAPTURE_SLOT_WINDOW_EXCEEDED")
    return {"status":"FRESH_CLAIM_V2_CAPTURE_REVIEW_REQUIRED",
        "gate_id":gate["gate_id"],"capture_slot":capture_slot,
        "current_slot":current_slot,"slot_age":current_slot-capture_slot,
        "message_sha256":capture["message_sha256"],
        "transaction_sha256":capture["transaction_sha256"],
        "mainnet_genesis_verified":True,"gate_consumed":False,
        "transaction_signed":False,"transaction_submitted":False,
        "execution_ready":False}


def bind_and_approve_fresh(path,closure,capture,signed_transaction,wallet,
                           confirmation,*,environment=None,post=None,current=None,
                           decoder=None,freshness_attestation=None):
    env=os.environ if environment is None else environment
    if freshness_attestation is None:
        freshness=inspect_fresh_capture(path,closure,capture,environment=env,post=post)
    else:
        from application.jupiter_claim_v2_blockhash_attestation import verify_blockhash_attestation
        freshness=verify_blockhash_attestation(path,closure,capture,
            freshness_attestation,environment=env,post=post)
    current=current or utc_now()
    bound=validate_wallet_signed_claim(path,closure,capture,signed_transaction,wallet,
        current=current,decoder=decoder)
    approval=approve_live_claim(path,bound["gate_id"],
        bound["signed_transaction_sha256"],confirmation,
        environment=env,current=current)
    return {"status":"FRESH_CLAIM_V2_WALLET_APPROVAL_BOUND",
        "gate_id":bound["gate_id"],"approval_id":approval["approval_id"],
        "approval_expires_at":approval["approval_expires_at"],
        "signed_transaction_sha256":bound["signed_transaction_sha256"],
        "capture_slot":capture.get("rpc_slot"),
        "slot_age":freshness.get("slot_age",freshness.get("attestation_slot_age")),
        "wallet_signature_verified":True,"submission_attempt_count":0,
        "transaction_submitted":False,"claim_submitted":False,
        "execution_ready":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate",required=True);parser.add_argument("--closure",required=True)
    parser.add_argument("--capture",required=True);parser.add_argument("--wallet",required=True)
    parser.add_argument("--signed-transaction-file",required=True)
    parser.add_argument("--confirm",required=True);args=parser.parse_args(argv)
    try:
        closure=_read_json(args.closure);capture=_read_json(args.capture)
        raw=open(args.signed_transaction_file,"rb").read(MAX_SIGNED_FILE_BYTES+1)
        require(len(raw)<=MAX_SIGNED_FILE_BYTES,"SIGNED_TRANSACTION_FILE_TOO_LARGE")
        report=bind_and_approve_fresh(args.gate,closure,capture,
            raw,args.wallet,args.confirm)
        print(json.dumps(report));return 2
    except ClaimV2GateRejected as error:reason=str(error)
    except Exception:reason="FRESH_CLAIM_APPROVAL_INPUT_OR_RPC_UNAVAILABLE"
    print(json.dumps({"status":"FRESH_CLAIM_V2_APPROVAL_NOT_BOUND","reason":reason,
        "transaction_submitted":False,"claim_submitted":False,"execution_ready":False}))
    return 1


if __name__=="__main__":raise SystemExit(main())
