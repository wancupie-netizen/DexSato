from types import SimpleNamespace
from application.jupiter_fee_disclosure import build_fee_disclosure
from application.jupiter_fee_policy import FeeEvidence, FeePolicy, WSOL_MINT
from application.jupiter_one_shot_swap_gate import CONFIRMATION, INPUT_LAMPORTS, REFERRAL, TAP_MINT, arm

def evidence(): return FeeEvidence(FeePolicy(True, REFERRAL, 50), WSOL_MINT)
def observation(*_args, **_kwargs):
    return SimpleNamespace(checked_at="2026-09-01T00:00:00+00:00", slot=1, partner_share_bps=8000)

def test_armed_exact_tap_contract_activates_fee_disclosure(tmp_path, monkeypatch):
    path=tmp_path/"gate.json";arm(path,CONFIRMATION)
    monkeypatch.setenv("DEXSATO_JUPITER_ONE_SHOT_MODE","true")
    monkeypatch.setenv("DEXSATO_JUPITER_ONE_SHOT_GATE_PATH",str(path))
    monkeypatch.setattr("application.jupiter_fee_disclosure.verify_referral_accounts",observation)
    value=build_fee_disclosure(evidence(),{"inAmount":str(INPUT_LAMPORTS),"gasless":False},INPUT_LAMPORTS,TAP_MINT)
    assert value["execution_ready"] is True and value["activation_scope"]=="ONE_SHOT_TAP"
    assert value["fee_receipt_verified"] is False

def test_one_shot_disclosure_fails_closed_for_other_output(tmp_path, monkeypatch):
    path=tmp_path/"gate.json";arm(path,CONFIRMATION)
    monkeypatch.setenv("DEXSATO_JUPITER_ONE_SHOT_MODE","true")
    monkeypatch.setenv("DEXSATO_JUPITER_ONE_SHOT_GATE_PATH",str(path))
    monkeypatch.setattr("application.jupiter_fee_disclosure.verify_referral_accounts",observation)
    value=build_fee_disclosure(evidence(),{"inAmount":str(INPUT_LAMPORTS),"gasless":False},INPUT_LAMPORTS,
                               "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    assert value["execution_ready"] is False and value["activation_scope"]=="PREVIEW_ONLY"
