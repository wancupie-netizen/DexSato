"""Read-only ClaimV2 gate, mainnet and funded-source inspection."""
from __future__ import annotations

import argparse
import hashlib
import json
import os

from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, _stamp, read_gate, require, utc_now,
)
from application.jupiter_claim_v2_submission import _endpoint, _signed
from application.jupiter_referral_verification import (
    MAINNET_GENESIS, referral_token_address,
)

MAX_SIGNED_FILE_BYTES=16_384

def _signed_read_only(value):
    if type(value) is bytes:
        require(1<=len(value)<=MAX_SIGNED_FILE_BYTES,"INVALID_SIGNED_TRANSACTION")
        return value
    return _signed(value)


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


def inspect_pre_execution(path,signed_transaction,approval_id,*,environment=None,
                          post=None,current=None):
    """Inspect exact approved evidence without mutating or consuming the gate."""
    env=os.environ if environment is None else environment
    require(env.get("DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED","false")
            .strip().lower()=="false","KEEP_LIVE_APPROVAL_DISABLED_DURING_INSPECTION")
    require(env.get("DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED","false")
            .strip().lower()=="false","KEEP_SUBMISSION_DISABLED_DURING_INSPECTION")
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED","false").strip().lower()=="false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    endpoint=_endpoint(env.get("SOLANA_RPC_URL",""))
    digest=hashlib.sha256(_signed_read_only(signed_transaction)).hexdigest()
    gate=read_gate(path);current=current or utc_now()
    require(current.tzinfo is not None,"INVALID_CLAIM_GATE_TIMESTAMP")
    require(gate.get("status")=="LIVE_CLAIM_APPROVED",
            "LIVE_CLAIM_APPROVAL_REQUIRED")
    require(current<=_stamp(gate.get("expires_at",""))
            and current<=_stamp(gate.get("approval_expires_at","")),
            "CLAIM_LIVE_APPROVAL_EXPIRED_OR_INVALID")
    require(gate.get("approval_id")==approval_id,"CLAIM_LIVE_APPROVAL_ID_MISMATCH")
    require(gate.get("signed_transaction_sha256")==digest
            and gate.get("approved_signed_transaction_sha256")==digest,
            "CLAIM_APPROVED_TRANSACTION_HASH_MISMATCH")
    require(gate.get("exact_claim_raw")=="5000"
            and gate.get("maximum_claim_raw")=="5000"
            and gate.get("expected_partner_raw")=="4000"
            and gate.get("expected_project_raw")=="1000",
            "CONTROLLED_CLAIM_AMOUNT_CONTRACT_MISMATCH")
    require(gate.get("wallet_review_count")==1 and gate.get("approval_count")==1
            and gate.get("submission_attempt_count")==0
            and gate.get("submission_permitted") is True
            and gate.get("claim_submitted") is False,
            "CLAIM_GATE_ALREADY_USED_OR_UNSAFE")
    genesis=_rpc(post,endpoint,"getGenesisHash",[])
    require(genesis==MAINNET_GENESIS,"SOLANA_MAINNET_GENESIS_MISMATCH")
    referral_ata=referral_token_address(gate.get("referral_account"),gate.get("mint"))
    balance=_rpc(post,endpoint,"getTokenAccountBalance",
        [referral_ata,{"commitment":"finalized"}])
    require(type(balance) is dict and type(balance.get("context")) is dict
            and type(balance["context"].get("slot")) is int
            and type(balance.get("value")) is dict,"INVALID_REFERRAL_BALANCE_RESPONSE")
    value=balance["value"];raw=value.get("amount")
    require(type(raw) is str and raw.isdigit()
            and type(value.get("decimals")) is int,"INVALID_REFERRAL_BALANCE_RESPONSE")
    require(raw=="5000","REFERRAL_FUNDED_BALANCE_NOT_EXACT")
    return {"status":"CLAIM_V2_PRE_EXECUTION_REVIEW_REQUIRED",
        "gate_id":gate["gate_id"],"signed_transaction_sha256":digest,
        "mainnet_genesis_verified":True,"referral_token_account":referral_ata,
        "referral_balance_raw":raw,"balance_slot":balance["context"]["slot"],
        "approval_expires_at":gate["approval_expires_at"],
        "gate_consumed":False,"rpc_methods":["getGenesisHash","getTokenAccountBalance"],
        "claim_submitted":False,"execution_ready":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate",required=True)
    parser.add_argument("--signed-transaction-file",required=True)
    parser.add_argument("--approval-id",required=True)
    args=parser.parse_args(argv)
    try:
        raw=open(args.signed_transaction_file,"rb").read(MAX_SIGNED_FILE_BYTES+1)
        require(len(raw)<=MAX_SIGNED_FILE_BYTES,"SIGNED_TRANSACTION_FILE_TOO_LARGE")
        report=inspect_pre_execution(args.gate,raw,
            args.approval_id)
        print(json.dumps(report));return 2
    except ClaimV2GateRejected as error:reason=str(error)
    except Exception:reason="PRE_EXECUTION_INPUT_OR_RPC_UNAVAILABLE"
    print(json.dumps({"status":"CLAIM_V2_PRE_EXECUTION_NOT_VERIFIED",
        "reason":reason,"gate_consumed":False,"claim_submitted":False,
        "execution_ready":False}));return 1


if __name__=="__main__":raise SystemExit(main())
