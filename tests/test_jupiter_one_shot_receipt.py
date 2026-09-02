import json
from application.jupiter_one_shot_receipt import verify
from application.jupiter_one_shot_swap_gate import arm,CONFIRMATION,record,_read,_write,REFERRAL_WSOL_ATA,REFERRAL
from application.jupiter_fee_policy import WSOL_MINT
from application.jupiter_referral_verification import TOKEN_PROGRAM
class R:
 status_code=200
 def __init__(self,p):self.p=p
 def json(self):return self.p
 def close(self):pass
def test_finalized_exact_referral_delta(tmp_path):
 p=tmp_path/'gate.json';g=arm(p,CONFIRMATION);g.update(status='CONSUMED');_write(p,g);record(p,'Success','sig')
 def post(*a,**k):
  item=lambda amount:{'accountIndex':0,'mint':WSOL_MINT,'owner':REFERRAL,'programId':TOKEN_PROGRAM,'uiTokenAmount':{'amount':str(amount)}}
  result={'slot':9,'transaction':{'message':{'accountKeys':[{'pubkey':REFERRAL_WSOL_ATA}]}},'meta':{'err':None,'preTokenBalances':[item(0)],'postTokenBalances':[item(5000)]}}
  return R({'jsonrpc':'2.0','id':1,'result':result})
 report=verify(p,'https://rpc.example',post)
 assert report['fee_receipt_verified'] is True and report['referral_delta_raw']=='5000'
