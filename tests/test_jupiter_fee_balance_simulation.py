import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace

import pytest
from solders.hash import Hash
from solders.instruction import CompiledInstruction
from solders.message import MessageHeader, MessageV0, to_bytes_versioned
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from application import jupiter_fee_balance_simulation as s
from application.jupiter_ata_lifecycle_binding import ATA, SYSTEM, canonical_ata
from application.jupiter_minimum_contract import MinimumContractRejected
from application.jupiter_order_identity_binding import TOKEN
from application.jupiter_referral_verification import MAINNET_GENESIS, referral_token_address

WALLET="J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
REFERRAL="5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
WSOL="So11111111111111111111111111111111111111112"
USDC="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
JUPITER="JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
EVENT="D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf"


def mint(decimals):
    raw=bytearray(82);raw[44]=decimals;raw[45]=1
    return {"owner":TOKEN,"executable":False,"data":[base64.b64encode(raw).decode(),"base64"]}


def fixture(now=None):
    now=now or datetime.now(timezone.utc);source=canonical_ata(WALLET,WSOL);destination=canonical_ata(WALLET,USDC)
    referral_ata=referral_token_address(REFERRAL,WSOL)
    addresses=[WALLET,source,destination,referral_ata,WSOL,USDC,TOKEN,ATA,SYSTEM,JUPITER,EVENT]
    keys=list(map(Pubkey.from_string,addresses))
    route=bytes.fromhex("bb64facc31c4af14")+(1_000_000).to_bytes(8,"little")+(103_637).to_bytes(8,"little")+(50).to_bytes(2,"little")+(50).to_bytes(2,"little")+bytes(2)+(1).to_bytes(4,"little")+b"\x59\x01\x10\x27\x00\x01"
    ix=[CompiledInstruction(7,b"\1",bytes([0,1,0,4,8,6])),
        CompiledInstruction(8,b"\2\0\0\0"+(1_000_000).to_bytes(8,"little"),bytes([0,1])),
        CompiledInstruction(6,b"\x11",bytes([1])),
        CompiledInstruction(7,b"\1",bytes([0,2,0,5,8,6])),
        CompiledInstruction(9,route,bytes([0,1,2,4,5,6,6,9,10,9,3])),
        CompiledInstruction(6,b"\x09",bytes([1,0,0]))]
    message=MessageV0(MessageHeader(1,0,7),keys,Hash.default(),ix,[])
    encoded=base64.b64encode(bytes(VersionedTransaction.populate(message,[Signature.default()]))).decode()
    digest=hashlib.sha256(to_bytes_versioned(message)).hexdigest()
    order={"transaction":encoded,"taker":WALLET,"inputMint":WSOL,"outputMint":USDC,
        "inAmount":"1000000","outAmount":"103637","otherAmountThreshold":"103118",
        "slippageBps":50,"referralAccount":REFERRAL,"feeMint":WSOL,"feeBps":50,
        "platformFee":{"feeBps":50,"feeMint":WSOL}}
    evidence={"quote":{k:v for k,v in order.items() if k not in {"transaction","taker"}},"order":order}
    intent={"wallet":WALLET,"input_mint":WSOL,"output_mint":USDC,
        "source_token_account":source,"destination_token_account":destination,
        "message_sha256":digest}
    snapshot={"context":{"slot":100},"accounts":{source:None,destination:None,WSOL:mint(9),USDC:mint(6)}}
    stamp=now.isoformat();capture={"captured_at":stamp,"message_sha256":digest}
    live={"checked_at":stamp,"message_sha256":digest,"status":"LIVE_IDENTITY_REVIEW_REQUIRED",
        "identity_snapshot_consistent":True,"execution_ready":False,"slot":100,
        "ata_lifecycle":{"lifecycle_instruction_order_verified":True}}
    return evidence,capture,live,snapshot,intent,referral_ata


class Response:
    status_code=200
    def __init__(self,result):self.result=result;self.closed=False
    def iter_content(self,chunk_size):
        yield json.dumps({"jsonrpc":"2.0","id":1,"result":self.result}).encode()
    def close(self):self.closed=True


def balance(index,amount):
    return {"accountIndex":index,"mint":WSOL,"owner":REFERRAL,"programId":TOKEN,
            "uiTokenAmount":{"amount":str(amount),"decimals":9,"uiAmountString":str(amount)}}


def run(monkeypatch,*,delta=5000,err=None,age=0,environment=None):
    now=datetime.now(timezone.utc);data=list(fixture(now-timedelta(seconds=age)))
    monkeypatch.setattr(s,"verify_referral_accounts",lambda *a,**k:SimpleNamespace(partner_share_bps=8000))
    calls=[]
    def post(url,*,json,**kwargs):
        calls.append(json)
        if json["method"]=="getGenesisHash":return Response(MAINNET_GENESIS)
        assert json["method"]=="simulateTransaction"
        value={"err":err,"unitsConsumed":200000,"logs":["Program success"],
            "innerInstructions":[],"preTokenBalances":[balance(3,10)],
            "postTokenBalances":[balance(3,10+delta)]}
        return Response({"context":{"slot":101},"value":value})
    env=environment or {"DEXSATO_JUPITER_FEE_ENABLED":"false",
        "DEXSATO_JUPITER_REFERRAL_ACCOUNT":REFERRAL,
        "DEXSATO_JUPITER_REFERRAL_PARTNER":WALLET,"SOLANA_RPC_URL":"https://rpc.example"}
    report=s.audit_simulation(*data[:5],environment=env,request_post=post,now=now)
    return report,calls,data


def test_atomic_simulation_token_delta_is_verified_without_submission(monkeypatch):
    report,calls,_=run(monkeypatch)
    assert report["status"]=="SIMULATED_GROSS_REFERRAL_ACCRUAL_REVIEW_REQUIRED"
    assert report["platform_fee_raw"]=="5000" and report["referral_delta_raw"]=="5000"
    assert report["provider_platform_fee_amount_present"] is False
    assert report["platform_fee_source"]=="DETERMINISTIC_INPUT_BPS_ARITHMETIC"
    assert report["simulation_gross_referral_accrual_verified"] is True
    assert report["expected_partner_claim_raw"]=="4000"
    assert report["partner_claim_delta_observed"] is False
    assert report["claim_split_verified"] is False
    assert report["execution_ready"] is False and report["fee_receipt_verified"] is False
    assert report["transaction_submitted"] is False and report["on_chain_receipt_verified"] is False
    config=calls[-1]["params"][1]
    assert config["sigVerify"] is False and config["replaceRecentBlockhash"] is True
    assert config["innerInstructions"] is True and config["minContextSlot"]==100


@pytest.mark.parametrize("delta",[0,3999,4000,4999,5001])
def test_wrong_referral_delta_fails_closed(monkeypatch,delta):
    with pytest.raises(MinimumContractRejected,match="REFERRAL_BALANCE_DELTA_MISMATCH"):
        run(monkeypatch,delta=delta)


def test_simulation_error_and_stale_evidence_fail_closed(monkeypatch):
    with pytest.raises(MinimumContractRejected,match="SIMULATION_FAILED"):run(monkeypatch,err={"InstructionError":[4,"Custom"]})
    with pytest.raises(MinimumContractRejected,match="EVIDENCE_NOT_FRESH"):run(monkeypatch,age=301)


def test_production_fee_flag_and_platform_fee_mismatch_stop_before_rpc(monkeypatch):
    env={"DEXSATO_JUPITER_FEE_ENABLED":"true"}
    with pytest.raises(MinimumContractRejected,match="KEEP_PRODUCTION_FEES_DISABLED"):run(monkeypatch,environment=env)
    now=datetime.now(timezone.utc);e,c,l,snap,i,_=fixture(now);e["order"]["platformFee"]["amount"]="4999"
    with pytest.raises(MinimumContractRejected,match="PLATFORM_FEE_AMOUNT_MISMATCH"):
        s.audit_simulation(e,c,l,snap,i,environment={"DEXSATO_JUPITER_FEE_ENABLED":"false",
            "DEXSATO_JUPITER_REFERRAL_ACCOUNT":REFERRAL},now=now)


def test_rpc_envelope_is_bounded_and_response_closed():
    response=Response(MAINNET_GENESIS)
    assert s.rpc("https://rpc.example","getGenesisHash",[],lambda *a,**k:response)==MAINNET_GENESIS
    assert response.closed is True
    with pytest.raises(MinimumContractRejected,match="HTTPS_RPC_CONFIGURATION_REQUIRED"):
        s.rpc("http://rpc.example","getGenesisHash",[],None)
