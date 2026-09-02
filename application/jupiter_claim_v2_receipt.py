"""Verify finalized ClaimV2 balance deltas against the consumed gate."""
from __future__ import annotations
import argparse,json,os
from urllib.parse import urlsplit
from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, read_gate, require, write_gate,
)
from application.jupiter_claim_v2_semantics import CLAIM_V2_DISCRIMINATOR, expected_accounts
from application.jupiter_referral_verification import REFERRAL_PROGRAM, TOKEN_PROGRAM

BASE58="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def _base58(value):
    require(type(value) is str and 1<=len(value)<=4096,"INVALID_CLAIM_INSTRUCTION_DATA")
    number=0
    try:
        for char in value:number=number*58+BASE58.index(char)
    except ValueError:raise ClaimV2GateRejected("INVALID_CLAIM_INSTRUCTION_DATA") from None
    body=number.to_bytes((number.bit_length()+7)//8,"big") if number else b""
    return b"\0"*(len(value)-len(value.lstrip("1")))+body

def _verify_instruction(result,expected):
    instructions=result.get("transaction",{}).get("message",{}).get("instructions") or []
    matches=[item for item in instructions if type(item) is dict
        and item.get("programId")==REFERRAL_PROGRAM]
    require(len(matches)==1,"CLAIM_V2_RECEIPT_INSTRUCTION_MISSING")
    item=matches[0]
    require(item.get("accounts")==[address for _,address in expected],
            "CLAIM_V2_RECEIPT_ACCOUNT_ORDER_MISMATCH")
    require(_base58(item.get("data"))[:8].hex()==CLAIM_V2_DISCRIMINATOR,
            "CLAIM_V2_RECEIPT_DISCRIMINATOR_MISMATCH")

def _amount(entries,index,mint,owner,allow_missing=False):
    found=[x for x in entries or [] if type(x) is dict and x.get("accountIndex")==index]
    if not found and allow_missing:return 0
    require(len(found)==1,"CLAIM_RECEIPT_BALANCE_MISSING")
    item=found[0];require(item.get("mint")==mint and item.get("owner")==owner
        and item.get("programId")==TOKEN_PROGRAM,"CLAIM_RECEIPT_IDENTITY_MISMATCH")
    raw=item.get("uiTokenAmount",{}).get("amount")
    require(type(raw) is str and raw.isdigit(),"INVALID_CLAIM_RECEIPT_AMOUNT")
    return int(raw)

def verify_claim_receipt(path,capture,endpoint,post=None):
    gate=read_gate(path);require(gate.get("status")=="FINALIZATION_PENDING"
        and gate.get("claim_submitted") is True,"FINALIZATION_PENDING_CLAIM_REQUIRED")
    parsed=urlsplit(endpoint);require(parsed.scheme=="https" and parsed.hostname
        and not parsed.username and not parsed.password,"HTTPS_RPC_CONFIGURATION_REQUIRED")
    response=None
    try:
        if post is None:
            import requests
            post=requests.post
        response=post(endpoint,json={"jsonrpc":"2.0","id":1,
          "method":"getTransaction","params":[gate["signature"],{"commitment":"finalized",
          "encoding":"jsonParsed","maxSupportedTransactionVersion":0}]},timeout=(3,20),allow_redirects=False)
        require(response.status_code==200,"RPC_HTTP_ERROR");payload=response.json()
        require(type(payload) is dict and payload.get("jsonrpc")=="2.0"
            and payload.get("id")==1 and payload.get("error") is None,
            "INVALID_RPC_RESPONSE")
        result=payload.get("result") if type(payload) is dict else None
        require(type(result) is dict and result.get("meta",{}).get("err") is None,
                "FINALIZED_CLAIM_NOT_AVAILABLE")
        require(type(capture) is dict and capture.get("transaction_sha256")==
            gate.get("unsigned_transaction_sha256") and capture.get("message_sha256")==
            gate.get("message_sha256"),"CLAIM_RECEIPT_CAPTURE_BINDING_MISMATCH")
        identity=capture.get("identity");expected=expected_accounts(identity)
        addresses=dict(expected);_verify_instruction(result,expected)
        require(identity.get("referral_account")==gate["referral_account"]
            and identity.get("partner")==gate["partner"]
            and identity.get("mint")==gate["mint"],"CLAIM_RECEIPT_GATE_IDENTITY_MISMATCH")
        keys=result.get("transaction",{}).get("message",{}).get("accountKeys") or []
        keys=[x.get("pubkey") if type(x) is dict else x for x in keys]
        roles=("referralTokenAccount","partnerTokenAccount","projectAdminTokenAccount")
        indexes={}
        for role in roles:
            matches=[i for i,key in enumerate(keys) if key==addresses[role]]
            require(len(matches)==1,"CLAIM_RECEIPT_ACCOUNT_MISSING");indexes[role]=matches[0]
        meta=result["meta"];mint=identity["mint"]
        ref_pre=_amount(meta.get("preTokenBalances"),indexes[roles[0]],mint,identity["referral_account"])
        ref_post=_amount(meta.get("postTokenBalances"),indexes[roles[0]],mint,identity["referral_account"])
        partner_pre=_amount(meta.get("preTokenBalances"),indexes[roles[1]],mint,identity["partner"],True)
        partner_post=_amount(meta.get("postTokenBalances"),indexes[roles[1]],mint,identity["partner"])
        admin_pre=_amount(meta.get("preTokenBalances"),indexes[roles[2]],mint,identity["admin"],True)
        admin_post=_amount(meta.get("postTokenBalances"),indexes[roles[2]],mint,identity["admin"])
        require((ref_pre-ref_post,partner_post-partner_pre,admin_post-admin_pre)==(5000,4000,1000),
                "FINALIZED_CLAIM_DELTA_MISMATCH")
        require(type(result.get("slot")) is int and result["slot"]>0,
                "INVALID_FINALIZED_SLOT")
        gate.update(status="FINALIZED_VERIFIED",finalized_slot=result.get("slot"),
          referral_delta_raw="-5000",partner_delta_raw="4000",project_admin_delta_raw="1000",
          claim_receipt_verified=True,execution_ready=False,claim_execution_ready=False)
        write_gate(path,gate)
        return {"status":"ONE_SHOT_CLAIM_V2_RECEIPT_FINALIZED_VERIFIED",
          "signature":gate["signature"],"slot":result.get("slot"),"referral_delta_raw":"-5000",
          "partner_delta_raw":"4000","project_admin_delta_raw":"1000",
          "claim_receipt_verified":True,"execution_ready":False}
    finally:
        if response is not None:response.close()

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate",required=True);parser.add_argument("--capture",required=True)
    args=parser.parse_args(argv)
    try:
        with open(args.capture,encoding="utf-8-sig") as stream:capture=json.load(stream)
        report=verify_claim_receipt(args.gate,capture,os.environ.get("SOLANA_RPC_URL",""))
        print(json.dumps(report));return 0
    except Exception as error:
        reason=str(error) if error.__class__.__name__=="ClaimV2GateRejected" else \
            "CLAIM_RECEIPT_INPUT_OR_OUTPUT_UNAVAILABLE"
        print(json.dumps({"status":"CLAIM_V2_RECEIPT_NOT_VERIFIED","reason":reason,
            "claim_receipt_verified":False,"execution_ready":False}));return 1

if __name__=="__main__":raise SystemExit(main())
