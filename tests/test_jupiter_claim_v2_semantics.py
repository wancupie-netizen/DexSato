import copy
import hashlib

import pytest

from application.jupiter_claim_v2_semantics import (
    ACCOUNT_ORDER_AUTHORITY, ACCOUNT_ROLES, CLAIM_V2_DISCRIMINATOR,
    PINNED_SDK_VERSION, ClaimV2AuditRejected,
    audit_claim_v2_instruction, expected_accounts,
)
from application.jupiter_fee_policy import WSOL_MINT
from application.jupiter_referral_verification import TOKEN_PROGRAM, ULTRA_PROJECT

PAYER = "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
REFERRAL = "5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
PARTNER = PAYER
ADMIN = "D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf"


def identity():
    # Permissionless claim payer may be the partner wallet.
    return {"payer": PARTNER,
            "project": ULTRA_PROJECT, "admin": ADMIN,
            "referral_account": REFERRAL, "partner": PARTNER,
            "mint": WSOL_MINT, "token_program": TOKEN_PROGRAM,
            "referral_share_bps": 8000}


def evidence():
    metas=[]
    for role,address in expected_accounts(identity()):
        metas.append({"role":role,"address":address,"signer":address==identity()["payer"],
                      "writable":role in {"payer","projectAdminTokenAccount",
                                           "referralTokenAccount","partnerTokenAccount"}})
    return {"program":"REFER4ZgmyYx9c6He5XfaTMiGfdLwRnkV4RPp9t9iF3",
            "discriminator":CLAIM_V2_DISCRIMINATOR,"accounts":metas}


def test_claim_v2_contract_is_pinned_and_always_non_executable():
    report=audit_claim_v2_instruction(evidence(),identity())
    assert report["status"]=="CLAIM_V2_SOURCE_ACCOUNT_REVIEW_REQUIRED"
    assert report["source_commit"]=="6500f64ff004e78faa15d66446e175ede625260d"
    assert report["account_count"]==12
    assert PINNED_SDK_VERSION=="0.3.0"
    assert report["account_order_authority"]==ACCOUNT_ORDER_AUTHORITY
    assert ACCOUNT_ROLES[9:]==("systemProgram","tokenProgram","associatedTokenProgram")
    assert [x["role"] for x in report["account_roles"]]==list(ACCOUNT_ROLES)
    assert report["source_semantics_verified"] is True
    assert report["deployed_program_binary_verified"] is False
    for field in ("claim_transaction_simulated","claim_split_verified","claim_submitted",
                  "controlled_live_swap_approved","production_fee_execution_enabled",
                  "execution_ready","fee_receipt_verified"):
        assert report[field] is False


def test_anchor_discriminator_is_derived_not_magic():
    assert CLAIM_V2_DISCRIMINATOR==hashlib.sha256(b"global:claim_v2").digest()[:8].hex()


def test_ultra_v2_referral_and_destination_atas_are_distinct():
    accounts=dict(expected_accounts(identity()))
    assert accounts["referralTokenAccount"]=="3vDQ2eA5mAu1Wf5podZ7rFRnamuMKC9prhaTkf8PvyUv"
    assert len({accounts["referralTokenAccount"],accounts["partnerTokenAccount"],
                accounts["projectAdminTokenAccount"]})==3
    assert accounts["payer"]==accounts["partner"]


@pytest.mark.parametrize("index",range(12))
def test_every_account_role_or_address_change_fails_closed(index):
    bad=evidence()
    current=bad["accounts"][index]["address"]
    bad["accounts"][index]["address"]=ADMIN if current != ADMIN else REFERRAL
    with pytest.raises(ClaimV2AuditRejected,match="CLAIM_V2_ACCOUNT_ADDRESS_MISMATCH"):
        audit_claim_v2_instruction(bad,identity())


def test_order_count_program_discriminator_and_signer_set_fail_closed():
    cases=[]
    bad=evidence();bad["accounts"].reverse();cases.append((bad,"CLAIM_V2_ACCOUNT_ORDER_MISMATCH"))
    bad=evidence();bad["accounts"].pop();cases.append((bad,"CLAIM_V2_ACCOUNT_COUNT_MISMATCH"))
    bad=evidence();bad["program"]=ADMIN;cases.append((bad,"REFERRAL_PROGRAM_MISMATCH"))
    bad=evidence();bad["discriminator"]="00"*8;cases.append((bad,"CLAIM_V2_DISCRIMINATOR_MISMATCH"))
    bad=evidence();bad["accounts"][2]["signer"]=True;cases.append((bad,"UNEXPECTED_CLAIM_SIGNER_SET"))
    for payload,code in cases:
        with pytest.raises(ClaimV2AuditRejected,match=code):
            audit_claim_v2_instruction(payload,identity())


def test_obsolete_source_literal_tail_order_is_rejected():
    """Object-literal order must not override the pinned compiled IDL order."""
    bad=evidence()
    bad["accounts"][9],bad["accounts"][10]=bad["accounts"][10],bad["accounts"][9]
    bad["accounts"][9]["role"]="tokenProgram"
    bad["accounts"][10]["role"]="systemProgram"
    with pytest.raises(ClaimV2AuditRejected,match="CLAIM_V2_ACCOUNT_ORDER_MISMATCH"):
        audit_claim_v2_instruction(bad,identity())


@pytest.mark.parametrize("role",["payer","projectAdminTokenAccount","referralTokenAccount","partnerTokenAccount"])
def test_required_writable_roles_cannot_be_downgraded(role):
    bad=evidence();next(x for x in bad["accounts"] if x["role"]==role)["writable"]=False
    with pytest.raises(ClaimV2AuditRejected,match="REQUIRED_WRITABLE_ACCOUNT_MISSING"):
        audit_claim_v2_instruction(bad,identity())


def test_identity_share_project_mint_and_token_program_are_fixed():
    mutations=[("referral_share_bps",7999,"REFERRAL_SHARE_REQUIRES_REVIEW"),
               ("project",ADMIN,"ULTRA_PROJECT_MISMATCH"),
               ("mint",ADMIN,"UNSUPPORTED_CLAIM_MINT"),
               ("token_program",ADMIN,"TOKEN_2022_NOT_REVIEWED")]
    for key,value,code in mutations:
        changed=identity();changed[key]=value
        with pytest.raises(ClaimV2AuditRejected,match=code):
            audit_claim_v2_instruction(evidence(),changed)


def test_module_contains_no_builder_signing_submission_or_rpc_path():
    import application.jupiter_claim_v2_semantics as module
    source=open(module.__file__,encoding="utf-8").read()
    for forbidden in ("sendTransaction","sendRawTransaction","simulateTransaction",
                      ".sign(","requests.","private_key","seed_phrase"):
        assert forbidden not in source
