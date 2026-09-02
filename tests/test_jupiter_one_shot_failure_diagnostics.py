from application.jupiter_fee_policy import FeePolicy
from application.jupiter_one_shot_swap_gate import (
    CONFIRMATION, INPUT_LAMPORTS, REFERRAL, TAP_MINT, WALLET,
    _read, arm, bind, consume, record, require_armed,
)

def _consumed_gate(tmp_path):
    path=tmp_path/"gate.json";arm(path,CONFIRMATION)
    gate=require_armed(path,TAP_MINT,WALLET,INPUT_LAMPORTS,FeePolicy(True,REFERRAL,50))
    message=b"reviewed-message";bind(path,gate,"request-1",message,"1")
    consume(path,"request-1",message,"ab"*32);return path

def test_failed_gate_records_bounded_safe_classification(tmp_path):
    path=_consumed_gate(tmp_path)
    record(path,"Failed",error="Transaction simulation failed: secret=https://rpc.invalid/key",code=6001)
    gate=_read(path)
    assert gate["status"]=="FAILED"
    assert gate["failure_reason"]=="TRANSACTION_SIMULATION_FAILED"
    assert gate["failure_code"]==6001
    assert "secret" not in str(gate) and "rpc.invalid" not in str(gate)

def test_unknown_or_invalid_failure_details_fail_closed(tmp_path):
    path=_consumed_gate(tmp_path);record(path,"Failed",error={"provider":"unreviewed"},code=True)
    gate=_read(path)
    assert gate["failure_reason"]=="JUPITER_EXECUTION_FAILED"
    assert gate["failure_code"] is None
