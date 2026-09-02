import base64
import copy
import runpy
from pathlib import Path

import pytest
from solders.instruction import CompiledInstruction
from solders.message import MessageHeader,MessageV0
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from application.jupiter_claim_v2_auxiliary import audit_auxiliary_instructions
from application.jupiter_claim_v2_semantics import ClaimV2AuditRejected, expected_accounts

sdk_helper=runpy.run_path(str(Path(__file__).with_name("test_jupiter_claim_v2_sdk_capture.py")))
identity=sdk_helper["identity"]
base_transaction=sdk_helper["unsigned_transaction"]


def transaction_with_auxiliary(*,bad_program=False,bad_data=False,bad_price=False,after=False):
    from application.jupiter_claim_v2_capture import _transaction
    tx,_=_transaction(base_transaction());message=tx.message
    keys=[str(key) for key in message.account_keys]
    compute="ComputeBudget111111111111111111111111111111"
    keys.append(compute);index={key:i for i,key in enumerate(keys)}
    accounts=dict(expected_accounts(identity()))
    owner_role={"projectAdminTokenAccount":"admin","referralTokenAccount":"referralAccount",
                "partnerTokenAccount":"partner"}
    price=1_000_001 if bad_price else 145_930
    instructions=[
        CompiledInstruction(index[accounts["tokenProgram"]] if bad_program else index[compute],
                            b"\x02"+(50_472).to_bytes(4,"little"),b""),
        CompiledInstruction(index[compute],b"\x03"+price.to_bytes(8,"little"),b""),
    ]
    role="partnerTokenAccount"
    addresses=[accounts["payer"],accounts[role],accounts[owner_role[role]],accounts["mint"],
               accounts["systemProgram"],accounts["tokenProgram"]]
    instructions.append(CompiledInstruction(index[accounts["associatedTokenProgram"]],
                        b"\x01" if bad_data else b"",bytes(index[x] for x in addresses)))
    claim=message.instructions[-1]
    instructions=instructions+[claim]
    if after:instructions=[claim]+instructions[:-1]
    header=MessageHeader(message.header.num_required_signatures,
        message.header.num_readonly_signed_accounts,
        message.header.num_readonly_unsigned_accounts+1)
    rebuilt=MessageV0(header,list(map(Pubkey.from_string,keys)),message.recent_blockhash,
                      instructions,message.address_table_lookups)
    return base64.b64encode(bytes(VersionedTransaction.populate(rebuilt,tx.signatures))).decode()


def capture_binding(encoded=None):
    from application.jupiter_claim_v2_capture import capture_claim_v2
    encoded=encoded or transaction_with_auxiliary()
    binding=capture_claim_v2(encoded,identity(),{"context":{"slot":100},"accounts":{}})
    binding.update(status="PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED",
                   execution_ready=False,fee_receipt_verified=False)
    capture={"status":"SDK_UNSIGNED_CAPTURED","transaction":encoded,"identity":identity(),
        "rpc_slot":100,"message_sha256":binding["message_sha256"],
        "transaction_sha256":binding["transaction_sha256"],"execution_ready":False,
        "fee_receipt_verified":False}
    return capture,binding


def test_three_exact_idempotent_atas_before_claim_are_allowlisted():
    capture,binding=capture_binding();report=audit_auxiliary_instructions(capture,binding)
    assert report["status"]=="CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED"
    assert [item["kind"] for item in report["decoded_instructions"]]==[
        "SET_COMPUTE_UNIT_LIMIT","SET_COMPUTE_UNIT_PRICE","CREATE_PARTNER_ATA","CLAIM_V2"]
    assert report["compute_unit_limit"]==50_472
    assert report["compute_unit_price_micro_lamports"]==145_930
    assert report["ata_create_destination"]=="partnerTokenAccount"
    assert report["auxiliary_instruction_semantics_verified"] is True
    assert report["execution_ready"] is False and report["fee_receipt_verified"] is False


@pytest.mark.parametrize("mutation,code",[
    ({"bad_program":True},"AUXILIARY_PROGRAM_NOT_ALLOWED"),
    ({"bad_data":True},"ATA_CREATE_DATA_MISMATCH"),
    ({"bad_price":True},"COMPUTE_UNIT_PRICE_OUT_OF_RANGE"),
    ({"after":True},"CLAIM_V2_MUST_BE_FINAL"),
])
def test_program_data_destination_order_and_final_claim_fail_closed(mutation,code):
    capture,binding=capture_binding(transaction_with_auxiliary(**mutation))
    with pytest.raises(ClaimV2AuditRejected,match=code):
        audit_auxiliary_instructions(capture,binding)


def test_hash_and_binding_status_mismatch_fail_closed():
    capture,binding=capture_binding()
    bad=copy.deepcopy(binding);bad["message_sha256"]="0"*64
    with pytest.raises(ClaimV2AuditRejected,match="CAPTURE_BINDING_HASH_MISMATCH"):
        audit_auxiliary_instructions(capture,bad)
    bad=copy.deepcopy(binding);bad["status"]="APPROVED"
    with pytest.raises(ClaimV2AuditRejected,match="COMPILED_BINDING_REQUIRED"):
        audit_auxiliary_instructions(capture,bad)


def test_decoder_has_no_network_signing_submission_or_simulation_path():
    import application.jupiter_claim_v2_auxiliary as module
    source=Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in ("requests.","httpx.","simulateTransaction","sendTransaction",
                      "sendRawTransaction",".sign(","Keypair","private_key","seed_phrase"):
        assert forbidden not in source
