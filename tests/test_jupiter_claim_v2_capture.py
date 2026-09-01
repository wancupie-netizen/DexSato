import base64
import copy

import pytest
from solders.hash import Hash
from solders.instruction import CompiledInstruction
from solders.message import MessageHeader,MessageV0
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from application.jupiter_claim_v2_capture import capture_claim_v2
from application.jupiter_claim_v2_semantics import (
    ACCOUNT_ROLES,CLAIM_V2_DISCRIMINATOR,ClaimV2AuditRejected,
    REFERRAL_PROGRAM,expected_accounts,
)
from application.jupiter_fee_policy import WSOL_MINT
from application.jupiter_referral_verification import TOKEN_PROGRAM,ULTRA_PROJECT

PARTNER="J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
REFERRAL="5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
ADMIN="D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf"


def identity():return {"payer":PARTNER,"project":ULTRA_PROJECT,"admin":ADMIN,
    "referral_account":REFERRAL,"partner":PARTNER,"mint":WSOL_MINT,
    "token_program":TOKEN_PROGRAM,"referral_share_bps":8000}


def transaction(*,signed=False,wrong_address=False,duplicate=False,extra=False):
    expected=list(expected_accounts(identity()))
    mapping=dict(expected)
    if wrong_address:mapping["admin"]=REFERRAL
    writable={"payer","projectAdminTokenAccount","referralTokenAccount","partnerTokenAccount"}
    signed_keys=[mapping["payer"]]
    unsigned_writable=[mapping[r] for r in ACCOUNT_ROLES if r in writable and r!="payer"]
    readonly=[]
    for role in ACCOUNT_ROLES:
        address=mapping[role]
        if role not in writable and address not in readonly:readonly.append(address)
    readonly.append(REFERRAL_PROGRAM)
    keys=[]
    for key in signed_keys+unsigned_writable+readonly:
        if key not in keys:keys.append(key)
    index={key:i for i,key in enumerate(keys)}
    account_indexes=[index[mapping[role]] for role in ACCOUNT_ROLES]
    if duplicate:account_indexes[-1]=account_indexes[-2]
    claim=CompiledInstruction(index[REFERRAL_PROGRAM],bytes.fromhex(CLAIM_V2_DISCRIMINATOR),
                              bytes(account_indexes))
    instructions=([CompiledInstruction(index[REFERRAL_PROGRAM],b"other",b"")] if extra else [])+[claim]
    header=MessageHeader(1,0,len(keys)-1-len(set(unsigned_writable)))
    message=MessageV0(header,list(map(Pubkey.from_string,keys)),Hash.default(),instructions,[])
    signature=Signature.from_bytes(bytes([1])*64) if signed else Signature.default()
    return base64.b64encode(bytes(VersionedTransaction.populate(message,[signature]))).decode()


def audit(encoded=None):return capture_claim_v2(encoded or transaction(),identity(),
                                                {"context":{"slot":100},"accounts":{}})


def test_unsigned_compiled_claim_is_bound_but_never_approved():
    report=audit()
    assert report["status"]=="UNSIGNED_CLAIM_V2_ACCOUNT_BINDING_REVIEW_REQUIRED"
    assert report["compiled_account_binding_verified"] is True
    assert report["claim_instruction_index"]==0 and report["account_roles"][0]["signer"] is True
    assert report["account_roles"][6]["address"]==PARTNER
    assert report["account_roles"][0]["address"]==PARTNER
    for field in ("snapshot_authenticity_verified","snapshot_freshness_verified",
                  "deployed_program_binary_verified","claim_transaction_simulated",
                  "claim_split_verified","claim_submitted","controlled_live_swap_approved",
                  "production_fee_execution_enabled","execution_ready","fee_receipt_verified"):
        assert report[field] is False


def test_auxiliary_instruction_is_reported_not_silently_attested():
    report=audit(transaction(extra=True))
    assert report["claim_instruction_index"]==1
    assert report["referral_instruction_count"]==2
    assert report["auxiliary_instructions_present"] is True
    assert report["auxiliary_instruction_semantics_verified"] is False


@pytest.mark.parametrize("mutation,code",[
    ({"signed":True},"TRANSACTION_IS_ALREADY_SIGNED"),
    ({"wrong_address":True},"CLAIM_V2_ACCOUNT_ADDRESS_MISMATCH"),
    ({"duplicate":True},"CLAIM_V2_ACCOUNT_ADDRESS_MISMATCH"),
])
def test_signed_address_mismatch_and_duplicate_indexes_fail_closed(mutation,code):
    with pytest.raises(ClaimV2AuditRejected,match=code):audit(transaction(**mutation))


def test_noncanonical_invalid_and_oversized_inputs_fail_closed():
    for encoded,code in (("not base64","INVALID_UNSIGNED_TRANSACTION"),
                         (base64.b64encode(b"x"*1233).decode(),"TRANSACTION_SIZE_LIMIT")):
        with pytest.raises(ClaimV2AuditRejected,match=code):audit(encoded)


def test_snapshot_shape_and_slot_are_bounded():
    encoded=transaction()
    with pytest.raises(ClaimV2AuditRejected,match="INVALID_SNAPSHOT_SLOT"):
        capture_claim_v2(encoded,identity(),{"context":{"slot":0},"accounts":{}})
    with pytest.raises(ClaimV2AuditRejected,match="INVALID_LOOKUP_SNAPSHOT"):
        capture_claim_v2(encoded,identity(),{"context":{"slot":1},"accounts":{},"extra":1})


def test_capture_module_has_no_network_sign_simulate_or_submit_path():
    import application.jupiter_claim_v2_capture as module
    source=open(module.__file__,encoding="utf-8").read()
    for forbidden in ("requests.","httpx.","sendTransaction","sendRawTransaction",
                      "simulateTransaction",".sign(","private_key","seed_phrase"):
        assert forbidden not in source
