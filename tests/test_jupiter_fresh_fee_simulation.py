from datetime import datetime, timezone

import pytest

from application import jupiter_fresh_fee_simulation as f
from application.jupiter_minimum_contract import MinimumContractRejected

WALLET="J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"


def test_one_shot_orchestrates_capture_identity_and_simulation(monkeypatch):
    calls=[]
    evidence={"order":{"transaction":"public"},"quote":{}}
    capture_report={"message_sha256":"a"*64}
    monkeypatch.setattr(f,"capture",lambda wallet,amount,fee,slip,**kw:
        (calls.append(("capture",wallet,amount,fee,slip)) or (evidence,capture_report)))
    monkeypatch.setattr(f,"capture_identity",lambda ev,intent,rpc,**kw:
        (calls.append(("identity",intent,rpc)) or
         ({"status":"LIVE_IDENTITY_REVIEW_REQUIRED"},{"accounts":{}})))
    expected={"status":"SIMULATED_GROSS_REFERRAL_ACCRUAL_REVIEW_REQUIRED",
              "execution_ready":False,"fee_receipt_verified":False}
    monkeypatch.setattr(f,"audit_simulation",lambda *a,**k:
        (calls.append(("simulation",a[4])) or expected))
    result=f.run(WALLET,environment={"SOLANA_RPC_URL":"https://rpc.example"},now=datetime.now(timezone.utc))
    assert calls[0]==("capture",WALLET,"1000000",50,50)
    assert calls[1][0]=="identity" and calls[2][0]=="simulation"
    assert result["simulation_report"]==expected
    assert result["intent"]["wallet"]==WALLET
    assert "private" not in str(result).lower() and "seed" not in str(result).lower()


def test_identity_failure_stops_before_simulation(monkeypatch):
    monkeypatch.setattr(f,"capture",lambda *a,**k:({"order":{},"quote":{}},{"message_sha256":"a"*64}))
    monkeypatch.setattr(f,"capture_identity",lambda *a,**k:({"status":"LIVE_IDENTITY_NOT_VERIFIED"},{}))
    called=[];monkeypatch.setattr(f,"audit_simulation",lambda *a,**k:called.append(1))
    with pytest.raises(MinimumContractRejected,match="LIVE_IDENTITY_NOT_VERIFIED"):
        f.run(WALLET,environment={"SOLANA_RPC_URL":"https://rpc.example"})
    assert called==[]


@pytest.mark.parametrize("stage,code",[
    ("capture","FRESH_ORDER_CAPTURE_UPSTREAM_UNAVAILABLE"),
    ("identity","FRESH_IDENTITY_SNAPSHOT_UPSTREAM_UNAVAILABLE"),
    ("simulation","FRESH_BALANCE_SIMULATION_UPSTREAM_UNAVAILABLE"),
])
def test_unexpected_errors_are_fixed_safe_stage_codes(monkeypatch,stage,code):
    evidence={"order":{},"quote":{}};report={"message_sha256":"a"*64}
    monkeypatch.setattr(f,"capture",lambda *a,**k:(evidence,report))
    monkeypatch.setattr(f,"capture_identity",lambda *a,**k:
        ({"status":"LIVE_IDENTITY_REVIEW_REQUIRED"},{}))
    monkeypatch.setattr(f,"audit_simulation",lambda *a,**k:{})
    if stage=="capture":monkeypatch.setattr(f,"capture",lambda *a,**k:(_ for _ in ()).throw(RuntimeError("secret upstream")))
    if stage=="identity":monkeypatch.setattr(f,"capture_identity",lambda *a,**k:(_ for _ in ()).throw(RuntimeError("secret rpc")))
    if stage=="simulation":monkeypatch.setattr(f,"audit_simulation",lambda *a,**k:(_ for _ in ()).throw(RuntimeError("secret simulation")))
    with pytest.raises(f.FreshSimulationStageError,match=f"^{code}$") as caught:
        f.run(WALLET,environment={"SOLANA_RPC_URL":"https://rpc.example"})
    assert "secret" not in str(caught.value)


def test_module_has_no_execution_or_signing_endpoint():
    from application import jupiter_fee_balance_simulation as balance
    source=open(f.__file__,encoding="utf-8").read()+open(balance.__file__,encoding="utf-8").read()
    for forbidden in ("/execute","sendTransaction","sendRawTransaction",".sign(","private_key","seed_phrase"):
        assert forbidden not in source
