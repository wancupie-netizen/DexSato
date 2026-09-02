"""Finalized on-chain receipt verifier for the consumed E.5 one-shot gate."""
import argparse,json,os
from urllib.parse import urlsplit
from application.jupiter_one_shot_swap_gate import (
    EXPECTED_FEE_RAW,REFERRAL,REFERRAL_WSOL_ATA,GateRejected,_read,_write,require,
)
from application.jupiter_referral_verification import TOKEN_PROGRAM
from application.jupiter_fee_policy import WSOL_MINT

def rpc(endpoint,signature,post=None):
    parsed=urlsplit(endpoint);require(parsed.scheme=="https" and parsed.hostname and not parsed.username and not parsed.password,"HTTPS_RPC_CONFIGURATION_REQUIRED")
    import requests
    response=(post or requests.post)(endpoint,json={"jsonrpc":"2.0","id":1,"method":"getTransaction","params":[signature,{"commitment":"finalized","encoding":"jsonParsed","maxSupportedTransactionVersion":0}]},timeout=(3,20),allow_redirects=False)
    try:
        require(response.status_code==200,"RPC_HTTP_ERROR");value=response.json()
        require(value.get("jsonrpc")=="2.0" and value.get("id")==1 and "error" not in value,"INVALID_RPC_ENVELOPE")
        return value.get("result")
    finally:response.close()
def amount(entries,index):
    found=[x for x in entries or [] if x.get("accountIndex")==index]
    require(len(found)==1,"REFERRAL_RECEIPT_BALANCE_MISSING")
    item=found[0];require(item.get("mint")==WSOL_MINT and item.get("owner")==REFERRAL and item.get("programId")==TOKEN_PROGRAM,"REFERRAL_RECEIPT_IDENTITY_MISMATCH")
    raw=item.get("uiTokenAmount",{}).get("amount");require(type(raw) is str and raw.isdigit(),"INVALID_RECEIPT_AMOUNT");return int(raw)
def verify(path,endpoint,post=None):
    gate=_read(path);require(gate.get("status")=="FINALIZATION_PENDING" and gate.get("signature"),"FINALIZATION_PENDING_GATE_REQUIRED")
    result=rpc(endpoint,gate["signature"],post);require(type(result) is dict and result.get("meta",{}).get("err") is None,"FINALIZED_TRANSACTION_NOT_AVAILABLE")
    keys=result.get("transaction",{}).get("message",{}).get("accountKeys") or []
    normalized=[x.get("pubkey") if type(x) is dict else x for x in keys]
    matches=[i for i,x in enumerate(normalized) if x==REFERRAL_WSOL_ATA];require(len(matches)==1,"REFERRAL_ATA_NOT_IN_RECEIPT")
    index=matches[0];meta=result["meta"];pre=amount(meta.get("preTokenBalances"),index);post_amount=amount(meta.get("postTokenBalances"),index)
    delta=post_amount-pre;require(delta==EXPECTED_FEE_RAW,"REFERRAL_RECEIPT_DELTA_MISMATCH")
    gate.update(status="FINALIZED_VERIFIED",finalized_slot=result.get("slot"),referral_pre_raw=str(pre),referral_post_raw=str(post_amount),referral_delta_raw=str(delta),fee_receipt_verified=True,execution_ready=False)
    _write(path,gate)
    return {"status":"ONE_SHOT_FEE_RECEIPT_FINALIZED_VERIFIED","signature":gate["signature"],"slot":result.get("slot"),"referral_delta_raw":str(delta),"execution_ready":False,"fee_receipt_verified":True}
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--gate",required=True);a=p.parse_args(argv)
    try:r=verify(a.gate,os.getenv("SOLANA_RPC_URL",""));print(json.dumps(r));return 0
    except Exception as e:
        reason=str(e) if isinstance(e,GateRejected) else "RECEIPT_RPC_OR_INPUT_UNAVAILABLE"
        print(json.dumps({"status":"ONE_SHOT_RECEIPT_NOT_VERIFIED","reason":reason,"execution_ready":False,"fee_receipt_verified":False}));return 1
if __name__=="__main__":raise SystemExit(main())
