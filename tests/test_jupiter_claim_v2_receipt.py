import copy

import pytest

from application.jupiter_claim_v2_one_shot_gate import ClaimV2GateRejected, read_gate, write_gate
from application.jupiter_claim_v2_receipt import verify_claim_receipt
from application.jupiter_claim_v2_semantics import CLAIM_V2_DISCRIMINATOR, expected_accounts
from application.jupiter_fee_policy import WSOL_MINT
from application.jupiter_referral_verification import REFERRAL_PROGRAM, TOKEN_PROGRAM, ULTRA_PROJECT

PARTNER="J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
REFERRAL="5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
ADMIN="D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf"


def identity(): return {"payer":PARTNER,"project":ULTRA_PROJECT,"admin":ADMIN,
    "referral_account":REFERRAL,"partner":PARTNER,"mint":WSOL_MINT,
    "token_program":TOKEN_PROGRAM,"referral_share_bps":8000}

BASE58="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
def b58(raw):
    zero=len(raw)-len(raw.lstrip(b"\0"));number=int.from_bytes(raw,"big");out=""
    while number:number,rem=divmod(number,58);out=BASE58[rem]+out
    return "1"*zero+out


class Response:
    status_code=200
    def __init__(self,payload): self.payload=payload
    def json(self): return self.payload
    def close(self): pass


def setup(tmp_path):
    path=tmp_path/"gate.json"
    write_gate(path,{"status":"FINALIZATION_PENDING","gate_id":"g"*32,
      "signature":"s"*88,"claim_submitted":True,"referral_account":REFERRAL,
      "partner":PARTNER,"mint":WSOL_MINT,"message_sha256":"a"*64,
      "unsigned_transaction_sha256":"b"*64,"submission_attempt_count":1,
      "execution_ready":False,"claim_execution_ready":False,
      "fee_receipt_verified":False},exclusive=True)
    capture={"message_sha256":"a"*64,"transaction_sha256":"b"*64,
             "identity":identity()}
    addresses=dict(expected_accounts(identity()))
    keys=[addresses["referralTokenAccount"],addresses["partnerTokenAccount"],
          addresses["projectAdminTokenAccount"]]
    def balance(index,owner,amount): return {"accountIndex":index,"mint":WSOL_MINT,
        "owner":owner,"programId":TOKEN_PROGRAM,"uiTokenAmount":{"amount":str(amount)}}
    result={"slot":443680900,"meta":{"err":None,
      "preTokenBalances":[balance(0,REFERRAL,5000)],
      "postTokenBalances":[balance(0,REFERRAL,0),balance(1,PARTNER,4000),
                            balance(2,ADMIN,1000)]},
      "transaction":{"message":{"accountKeys":keys,"instructions":[{
        "programId":REFERRAL_PROGRAM,"accounts":[x[1] for x in expected_accounts(identity())],
        "data":b58(bytes.fromhex(CLAIM_V2_DISCRIMINATOR))}]}}}
    return path,capture,result


def request(result):
    return lambda *a,**k: Response({"jsonrpc":"2.0","id":1,"result":result})


def test_exact_finalized_80_20_claim_receipt_closes_gate(tmp_path):
    path,capture,result=setup(tmp_path)
    report=verify_claim_receipt(path,capture,"https://rpc.example/key",post=request(result))
    assert report["status"]=="ONE_SHOT_CLAIM_V2_RECEIPT_FINALIZED_VERIFIED"
    assert report["claim_receipt_verified"] is True
    assert report["execution_ready"] is False
    gate=read_gate(path)
    assert gate["status"]=="FINALIZED_VERIFIED"
    assert gate["submission_attempt_count"]==1


@pytest.mark.parametrize("mutation,code",[
    ("delta","FINALIZED_CLAIM_DELTA_MISMATCH"),
    ("error","FINALIZED_CLAIM_NOT_AVAILABLE"),
    ("account","CLAIM_RECEIPT_ACCOUNT_MISSING"),
    ("instruction","CLAIM_V2_RECEIPT_DISCRIMINATOR_MISMATCH"),
    ("capture","CLAIM_RECEIPT_CAPTURE_BINDING_MISMATCH"),
])
def test_mismatch_never_closes_gate(tmp_path,mutation,code):
    path,capture,result=setup(tmp_path);result=copy.deepcopy(result)
    if mutation=="delta": result["meta"]["postTokenBalances"][1]["uiTokenAmount"]["amount"]="3999"
    elif mutation=="error": result["meta"]["err"]={"InstructionError":[3,"Custom"]}
    elif mutation=="account": result["transaction"]["message"]["accountKeys"][1]="11111111111111111111111111111111"
    elif mutation=="instruction": result["transaction"]["message"]["instructions"][0]["data"]="1"
    else: capture["message_sha256"]="c"*64
    with pytest.raises(ClaimV2GateRejected,match=code):
        verify_claim_receipt(path,capture,"https://rpc.example/key",post=request(result))
    assert read_gate(path)["status"]=="FINALIZATION_PENDING"
