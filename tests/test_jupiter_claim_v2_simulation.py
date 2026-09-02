import copy
import json
import runpy
from pathlib import Path

import pytest

from application import jupiter_claim_v2_simulation as simulation
from application.jupiter_claim_v2_semantics import ClaimV2AuditRejected, expected_accounts
from application.jupiter_referral_verification import MAINNET_GENESIS

helper = runpy.run_path(str(Path(__file__).with_name("test_jupiter_claim_v2_sdk_capture.py")))
identity = helper["identity"]
aux_helper = runpy.run_path(str(Path(__file__).with_name("test_jupiter_claim_v2_auxiliary.py")))
transaction = aux_helper["transaction_with_auxiliary"]


class Response:
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def iter_content(self, chunk_size=8192): yield json.dumps(self.payload).encode()
    def close(self): pass


def capture_and_binding():
    encoded = transaction()
    from application.jupiter_claim_v2_capture import capture_claim_v2
    bound = capture_claim_v2(encoded, identity(), {"context":{"slot":100},"accounts":{}})
    bound.update(status="PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED",
                 sdk_version="0.3.0", execution_ready=False,
                 fee_receipt_verified=False)
    capture = {"status":"SDK_UNSIGNED_CAPTURED","transaction":encoded,
        "identity":identity(),"rpc_slot":100,
        "message_sha256":bound["message_sha256"],
        "transaction_sha256":bound["transaction_sha256"],
        "sdk_version":"0.3.0","execution_ready":False,
        "fee_receipt_verified":False}
    return capture, bound


def balances(capture, referral=(10_000,0), partner=(1_000,9_000), admin=(2_000,4_000),
             omit_pre_role=None,omit_post_role=None):
    from application.jupiter_claim_v2_capture import _transaction
    tx,_ = _transaction(capture["transaction"])
    keys = [str(key) for key in tx.message.account_keys]
    accounts = dict(expected_accounts(capture["identity"]))
    result_pre=[];result_post=[]
    for role, owner, amounts in (
        ("referralTokenAccount",capture["identity"]["referral_account"],referral),
        ("partnerTokenAccount",capture["identity"]["partner"],partner),
        ("projectAdminTokenAccount",capture["identity"]["admin"],admin)):
        index=keys.index(accounts[role])
        for target, amount in ((result_pre,amounts[0]),(result_post,amounts[1])):
            if target is result_pre and role==omit_pre_role:continue
            if target is result_post and role==omit_post_role:continue
            target.append({"accountIndex":index,"mint":capture["identity"]["mint"],
                "owner":owner,"programId":capture["identity"]["token_program"],
                "uiTokenAmount":{"amount":str(amount)}})
    return result_pre,result_post


def post(capture, *, referral=(10_000,0), partner=(1_000,9_000), admin=(2_000,4_000),
         err=None, genesis=MAINNET_GENESIS,omit_pre_role=None,omit_post_role=None):
    pre,post_balances=balances(capture,referral,partner,admin,omit_pre_role,omit_post_role)
    def request(url, **kwargs):
        method=kwargs["json"]["method"]
        result=genesis if method=="getGenesisHash" else {
            "context":{"slot":101},"value":{"err":err,"unitsConsumed":100_000,
            "preTokenBalances":pre,"postTokenBalances":post_balances,
            "logs":["Program log: simulated"],"innerInstructions":[]}}
        return Response({"jsonrpc":"2.0","id":1,"result":result})
    return request


def audit(**kwargs):
    capture,binding=capture_and_binding()
    request=post(capture,**kwargs)
    auxiliary={"status":"CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED",
        "message_sha256":capture["message_sha256"],
        "transaction_sha256":capture["transaction_sha256"],
        "auxiliary_instruction_semantics_verified":True,
        "ata_create_destination":"partnerTokenAccount",
        "execution_ready":False,"fee_receipt_verified":False}
    return simulation.audit_claim_simulation(capture,binding,auxiliary,
        environment={"DEXSATO_JUPITER_FEE_ENABLED":"false",
                     "SOLANA_RPC_URL":"https://rpc.example/key"},request_post=request)


def test_exact_simulated_80_20_split_is_review_only():
    report=audit()
    assert report["status"]=="CLAIM_V2_SIMULATION_BALANCE_DELTA_REVIEW_REQUIRED"
    assert report["gross_claim_raw"]=="10000"
    assert report["partner_delta_raw"]=="8000"
    assert report["project_admin_delta_raw"]=="2000"
    assert report["simulated_claim_split_verified"] is True
    assert report["balance_conservation_verified"] is True
    assert report["account_order_authority"]=="PINNED_SDK_COMPILED_IDL"
    for field in ("transaction_signed","transaction_submitted","claim_submitted",
                  "controlled_live_swap_approved","production_fee_execution_enabled",
                  "execution_ready","fee_receipt_verified","on_chain_receipt_verified"):
        assert report[field] is False


def test_floor_partner_and_remainder_project_semantics_are_exact():
    report=audit(referral=(10_003,0),partner=(50,8_052),admin=(70,2_071))
    assert report["partner_delta_raw"]=="8002"
    assert report["project_admin_delta_raw"]=="2001"


def test_created_partner_ata_missing_pre_balance_is_classified_as_exact_zero():
    report=audit(partner=(0,8_000),omit_pre_role="partnerTokenAccount")
    assert report["partner_pre_raw"]=="0"
    assert report["partner_pre_source"]=="CREATED_ATA_IMPLICIT_ZERO"
    assert report["partner_delta_raw"]=="8000"
    assert report["simulated_claim_split_verified"] is True


@pytest.mark.parametrize("role",["referralTokenAccount","projectAdminTokenAccount"])
def test_non_created_source_pre_balance_cannot_be_implicit_zero(role):
    with pytest.raises(ClaimV2AuditRejected,match="CLAIM_TOKEN_BALANCE_MISSING_OR_AMBIGUOUS"):
        audit(omit_pre_role=role)


@pytest.mark.parametrize("role",[
    "referralTokenAccount","partnerTokenAccount","projectAdminTokenAccount"])
def test_every_post_balance_remains_mandatory(role):
    with pytest.raises(ClaimV2AuditRejected,match="CLAIM_TOKEN_BALANCE_MISSING_OR_AMBIGUOUS"):
        audit(omit_post_role=role)


@pytest.mark.parametrize("kwargs,code",[
    ({"partner":(1_000,8_999)},"PARTNER_CLAIM_DELTA_MISMATCH"),
    ({"admin":(2_000,3_999)},"PROJECT_ADMIN_CLAIM_DELTA_MISMATCH"),
    ({"referral":(0,0),"partner":(1,1),"admin":(1,1)},"REFERRAL_SOURCE_DELTA_INVALID"),
    ({"err":{"InstructionError":[0,"Custom"]}},"CLAIM_V2_SIMULATION_FAILED"),
    ({"genesis":"wrong-chain"},"RPC_IS_NOT_SOLANA_MAINNET"),
])
def test_delta_error_and_chain_mismatch_fail_closed(kwargs,code):
    with pytest.raises(ClaimV2AuditRejected,match=code): audit(**kwargs)


def test_capture_hash_status_and_execution_flag_mismatch_fail_closed():
    capture,binding=capture_and_binding()
    cases=[]
    bad=copy.deepcopy(capture);bad["message_sha256"]="0"*64;cases.append((bad,binding,"CAPTURE_BINDING_HASH_MISMATCH"))
    bad=copy.deepcopy(binding);bad["status"]="APPROVED";cases.append((capture,bad,"COMPILED_BINDING_REQUIRED"))
    bad=copy.deepcopy(capture);bad["execution_ready"]=True;cases.append((bad,binding,"PINNED_CAPTURE_REQUIRED"))
    for candidate,report,code in cases:
        with pytest.raises(ClaimV2AuditRejected,match=code):
            auxiliary={"status":"CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED",
                "message_sha256":candidate.get("message_sha256"),
                "transaction_sha256":candidate.get("transaction_sha256"),
                "auxiliary_instruction_semantics_verified":True,
                "ata_create_destination":"partnerTokenAccount",
                "execution_ready":False,"fee_receipt_verified":False}
            simulation.validate_capture(candidate,report,auxiliary)


def test_enabled_fee_non_https_rpc_and_duplicate_json_fail_closed():
    capture,binding=capture_and_binding()
    from application.jupiter_claim_v2_auxiliary import audit_auxiliary_instructions
    auxiliary=audit_auxiliary_instructions(capture,binding)
    with pytest.raises(ClaimV2AuditRejected,match="KEEP_PRODUCTION_FEES_DISABLED"):
        simulation.audit_claim_simulation(capture,binding,auxiliary,
            environment={"DEXSATO_JUPITER_FEE_ENABLED":"true"})
    with pytest.raises(ClaimV2AuditRejected,match="HTTPS_RPC_CONFIGURATION_REQUIRED"):
        simulation.audit_claim_simulation(capture,binding,auxiliary,
            environment={"DEXSATO_JUPITER_FEE_ENABLED":"false","SOLANA_RPC_URL":"http://rpc"})
    with pytest.raises(ClaimV2AuditRejected,match="DUPLICATE_JSON_KEY"):
        simulation.strict_json(b'{"a":1,"a":2}')


def test_module_has_no_signing_or_submission_api():
    source=Path(simulation.__file__).read_text(encoding="utf-8")
    for forbidden in ("sendTransaction","sendRawTransaction","sendAndConfirm",
                      ".sign(","Keypair","private_key","seed_phrase"):
        assert forbidden not in source
