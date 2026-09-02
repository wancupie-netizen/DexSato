"""Persistent one-shot approval gate for one controlled TAP fee-bearing swap."""
from __future__ import annotations
import argparse,hashlib,json,os,secrets
from datetime import datetime,timedelta,timezone
from pathlib import Path

TAP_MINT="ADcF26nFGKMuRZ7va5361H2PCHCDRi2FmeJBkX3Spump"
WALLET="J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
REFERRAL="5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
REFERRAL_WSOL_ATA="3vDQ2eA5mAu1Wf5podZ7rFRnamuMKC9prhaTkf8PvyUv"
INPUT_LAMPORTS=1_000_000;FEE_BPS=50;EXPECTED_FEE_RAW=5_000
CONFIRMATION="I APPROVE ONE CONTROLLED TAP FEE SWAP"

class GateRejected(RuntimeError):pass
def require(ok,code):
    if not ok:raise GateRejected(code)
def now():return datetime.now(timezone.utc)
def _stamp(value):
    try:return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception:raise GateRejected("INVALID_GATE_TIMESTAMP") from None
def _read(path):
    raw=Path(path).read_bytes();require(len(raw)<=32768,"GATE_FILE_TOO_LARGE")
    def unique(pairs):
        out={}
        for k,v in pairs:require(k not in out,"DUPLICATE_JSON_KEY");out[k]=v
        return out
    try:value=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=unique)
    except GateRejected:raise
    except Exception:raise GateRejected("INVALID_GATE_FILE") from None
    require(type(value) is dict,"INVALID_GATE_FILE");return value
def _write(path,value,exclusive=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(value,indent=2,sort_keys=True)+"\n"
    if exclusive:
        with path.open("x",encoding="utf-8",newline="\n") as f:f.write(data)
    else:
        temporary=path.with_name(path.name+".tmp")
        with temporary.open("x",encoding="utf-8",newline="\n") as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
def arm(path,confirmation,current=None):
    require(confirmation==CONFIRMATION,"EXPLICIT_CONFIRMATION_REQUIRED")
    current=current or now();gate={"version":1,"gate_id":secrets.token_hex(16),"status":"ARMED",
      "wallet":WALLET,"output_mint":TAP_MINT,"input_lamports":str(INPUT_LAMPORTS),
      "referral_account":REFERRAL,"referral_wsol_ata":REFERRAL_WSOL_ATA,
      "fee_bps":FEE_BPS,"expected_fee_raw":str(EXPECTED_FEE_RAW),
      "armed_at":current.isoformat(),"expires_at":(current+timedelta(minutes=10)).isoformat(),
      "attempt_count":0,"execution_ready":False,"fee_receipt_verified":False}
    _write(path,gate,True);return gate
def require_armed(path,token,wallet,lamports,policy,current=None):
    gate=_read(path);current=current or now()
    require(gate.get("status")=="ARMED","ONE_SHOT_GATE_NOT_ARMED")
    require(current<=_stamp(gate.get("expires_at","")),"ONE_SHOT_GATE_EXPIRED")
    require(token==TAP_MINT==gate.get("output_mint") and wallet==WALLET==gate.get("wallet"),"ONE_SHOT_IDENTITY_MISMATCH")
    require(lamports==INPUT_LAMPORTS and gate.get("input_lamports")==str(INPUT_LAMPORTS),"ONE_SHOT_AMOUNT_MISMATCH")
    require(policy.enabled and policy.referral_account==REFERRAL and policy.fee_bps==FEE_BPS,"ONE_SHOT_FEE_POLICY_MISMATCH")
    return gate
def bind(path,gate,request_id,message,minimum):
    current=_read(path);require(current.get("gate_id")==gate.get("gate_id") and current.get("status")=="ARMED","ONE_SHOT_GATE_CHANGED")
    current.update(status="BOUND",request_id=request_id,message_sha256=hashlib.sha256(message).hexdigest(),minimum_received_raw=minimum,bound_at=now().isoformat())
    _write(path,current);return current
def consume(path,request_id,message,signed_digest):
    gate=_read(path);digest=hashlib.sha256(message).hexdigest()
    require(gate.get("status") in {"BOUND","CONSUMED"},"ONE_SHOT_GATE_NOT_BOUND")
    require(gate.get("request_id")==request_id and gate.get("message_sha256")==digest,"ONE_SHOT_ORDER_BINDING_MISMATCH")
    if gate["status"]=="CONSUMED":
        require(gate.get("signed_sha256")==signed_digest,"ONE_SHOT_RETRY_TRANSACTION_MISMATCH");return gate
    gate.update(status="CONSUMED",signed_sha256=signed_digest,attempt_count=1,consumed_at=now().isoformat())
    _write(path,gate);return gate
def _safe_failure(error,code):
    text=str(error or "").casefold()
    if "insufficient" in text and ("fund" in text or "balance" in text):reason="INSUFFICIENT_SOL_BALANCE"
    elif "slippage" in text or "minimum output" in text:reason="SLIPPAGE_OR_MINIMUM_OUTPUT"
    elif "blockhash" in text or "expired" in text:reason="BLOCKHASH_EXPIRED"
    elif "account" in text and ("invalid" in text or "not found" in text):reason="ACCOUNT_STATE_INVALID"
    elif "simulation" in text:reason="TRANSACTION_SIMULATION_FAILED"
    else:reason="JUPITER_EXECUTION_FAILED"
    safe_code=code if type(code) is int and -1_000_000_000<=code<=1_000_000_000 else None
    return reason,safe_code
def record(path,status,signature=None,error=None,code=None):
    gate=_read(path);require(gate.get("status")=="CONSUMED","ONE_SHOT_GATE_NOT_CONSUMED")
    gate.update(status="FINALIZATION_PENDING" if status=="Success" else "FAILED",provider_status=status,signature=signature,result_recorded_at=now().isoformat())
    if status!="Success":
        reason,safe_code=_safe_failure(error,code)
        gate.update(failure_reason=reason,failure_code=safe_code)
    _write(path,gate);return gate
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);p.add_argument("--confirm",required=True);a=p.parse_args(argv)
    try:g=arm(a.output,a.confirm);print(json.dumps({"status":g["status"],"gate_id":g["gate_id"],"expires_at":g["expires_at"],"execution_ready":False}));return 0
    except GateRejected as e:print(json.dumps({"status":"NOT_ARMED","reason":str(e),"execution_ready":False}));return 1
if __name__=="__main__":raise SystemExit(main())
