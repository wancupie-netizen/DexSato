import base64,hashlib
from datetime import datetime,timedelta,timezone

import pytest

from application.jupiter_claim_v2_one_shot_gate import ClaimV2GateRejected,read_gate,write_gate
from application.jupiter_claim_v2_pre_execution import inspect_pre_execution
from application.jupiter_fee_policy import WSOL_MINT
from application.jupiter_referral_verification import MAINNET_GENESIS

NOW=datetime(2026,9,2,13,0,tzinfo=timezone.utc);RAW=b"wallet-signed-claim"
SIGNED=base64.b64encode(RAW).decode();DIGEST=hashlib.sha256(RAW).hexdigest();APPROVAL="a"*32

class Response:
 status_code=200
 def __init__(self,value):self.value=value
 def json(self):return self.value
 def close(self):pass

def gate(tmp_path,**changes):
 path=tmp_path/"gate.json";value={"gate_id":"g"*32,"status":"LIVE_CLAIM_APPROVED",
  "expires_at":(NOW+timedelta(minutes=3)).isoformat(),"approval_expires_at":(NOW+timedelta(seconds=90)).isoformat(),
  "approval_id":APPROVAL,"approval_count":1,"wallet_review_count":1,"submission_attempt_count":0,
  "signed_transaction_sha256":DIGEST,"approved_signed_transaction_sha256":DIGEST,
  "submission_permitted":True,"claim_submitted":False,"exact_claim_raw":"5000",
  "maximum_claim_raw":"5000","expected_partner_raw":"4000","expected_project_raw":"1000",
  "referral_account":"5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ","mint":WSOL_MINT,
  "execution_ready":False};value.update(changes);write_gate(path,value,exclusive=True);return path

def env(**changes):return {"DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED":"false",
 "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED":"false","DEXSATO_JUPITER_FEE_ENABLED":"false",
 "SOLANA_RPC_URL":"https://rpc.example/key",**changes}

def provider(*,genesis=MAINNET_GENESIS,amount="5000"):
 calls=[]
 def post(url,**kwargs):
  method=kwargs["json"]["method"];calls.append(method)
  result=genesis if method=="getGenesisHash" else {"context":{"slot":443700000},
    "value":{"amount":amount,"decimals":9,"uiAmountString":"0.000005"}}
  return Response({"jsonrpc":"2.0","id":1,"result":result})
 return calls,post

def test_exact_read_only_inspection_does_not_consume_gate(tmp_path):
 path=gate(tmp_path);before=path.read_bytes();calls,post=provider()
 report=inspect_pre_execution(path,SIGNED,APPROVAL,environment=env(),post=post,current=NOW)
 assert report["status"]=="CLAIM_V2_PRE_EXECUTION_REVIEW_REQUIRED"
 assert report["referral_balance_raw"]=="5000" and report["execution_ready"] is False
 assert calls==["getGenesisHash","getTokenAccountBalance"]
 assert path.read_bytes()==before and read_gate(path)["submission_attempt_count"]==0

def test_exact_raw_binary_inspection_does_not_consume_gate(tmp_path):
 path=gate(tmp_path);before=path.read_bytes();calls,post=provider()
 report=inspect_pre_execution(path,RAW,APPROVAL,environment=env(),post=post,current=NOW)
 assert report["signed_transaction_sha256"]==DIGEST
 assert path.read_bytes()==before and calls==["getGenesisHash","getTokenAccountBalance"]

@pytest.mark.parametrize("amount",["0","4999","5001"])
def test_non_exact_funded_balance_is_rejected_without_consumption(tmp_path,amount):
 path=gate(tmp_path);calls,post=provider(amount=amount)
 with pytest.raises(ClaimV2GateRejected,match="REFERRAL_FUNDED_BALANCE_NOT_EXACT"):
  inspect_pre_execution(path,SIGNED,APPROVAL,environment=env(),post=post,current=NOW)
 assert read_gate(path)["submission_attempt_count"]==0

def test_wrong_network_stops_before_balance_query(tmp_path):
 path=gate(tmp_path);calls,post=provider(genesis="devnet")
 with pytest.raises(ClaimV2GateRejected,match="SOLANA_MAINNET_GENESIS_MISMATCH"):
  inspect_pre_execution(path,SIGNED,APPROVAL,environment=env(),post=post,current=NOW)
 assert calls==["getGenesisHash"] and read_gate(path)["submission_attempt_count"]==0

@pytest.mark.parametrize("changes,code",[
 ({"DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED":"true"},"KEEP_SUBMISSION_DISABLED_DURING_INSPECTION"),
 ({"DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED":"true"},"KEEP_LIVE_APPROVAL_DISABLED_DURING_INSPECTION")])
def test_any_execution_flag_blocks_read_only_inspection(tmp_path,changes,code):
 calls,post=provider()
 with pytest.raises(ClaimV2GateRejected,match=code):
  inspect_pre_execution(gate(tmp_path),SIGNED,APPROVAL,environment=env(**changes),post=post,current=NOW)
 assert calls==[]
