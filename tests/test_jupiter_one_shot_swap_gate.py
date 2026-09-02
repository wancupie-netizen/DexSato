from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from application.jupiter_fee_policy import FeePolicy
from application.jupiter_one_shot_swap_gate import *

def test_gate_arms_binds_consumes_once_and_allows_identical_poll(tmp_path):
 p=tmp_path/"gate.json";g=arm(p,CONFIRMATION,datetime(2026,9,1,tzinfo=timezone.utc))
 policy=FeePolicy(True,REFERRAL,50)
 g=require_armed(p,TAP_MINT,WALLET,INPUT_LAMPORTS,policy,datetime(2026,9,1,tzinfo=timezone.utc))
 bound=bind(p,g,"request-1",b"message","100")
 consumed=consume(p,"request-1",b"message","signed")
 assert consumed["status"]=="CONSUMED" and consumed["attempt_count"]==1
 assert consume(p,"request-1",b"message","signed")["attempt_count"]==1
 with pytest.raises(GateRejected):consume(p,"request-1",b"message","changed")
 assert record(p,"Success","sig")["status"]=="FINALIZATION_PENDING"

@pytest.mark.parametrize("token,wallet,amount,bps",[
 ("bad",WALLET,INPUT_LAMPORTS,50),(TAP_MINT,"bad",INPUT_LAMPORTS,50),
 (TAP_MINT,WALLET,INPUT_LAMPORTS+1,50),(TAP_MINT,WALLET,INPUT_LAMPORTS,51)])
def test_every_scope_change_fails_closed(tmp_path,token,wallet,amount,bps):
 p=tmp_path/"gate.json";arm(p,CONFIRMATION)
 with pytest.raises(GateRejected):require_armed(p,token,wallet,amount,FeePolicy(True,REFERRAL,bps))

def test_confirmation_and_rearm_fail(tmp_path):
 p=tmp_path/"gate.json"
 with pytest.raises(GateRejected):arm(p,"yes")
 arm(p,CONFIRMATION)
 with pytest.raises(FileExistsError):arm(p,CONFIRMATION)
