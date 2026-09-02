"""Offline decoder and exact allowlist for pinned-SDK ClaimV2 auxiliaries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from application.jupiter_claim_v2_capture import _transaction, capture_claim_v2
from application.jupiter_claim_v2_semantics import (
    CLAIM_V2_DISCRIMINATOR, REFERRAL_PROGRAM, SYSTEM_PROGRAM,
    ClaimV2AuditRejected, expected_accounts, require,
)
from application.jupiter_referral_verification import ASSOCIATED_TOKEN_PROGRAM, TOKEN_PROGRAM

MAX_JSON_BYTES=524_288
ATA_IDEMPOTENT_DATA=b"\x01"
COMPUTE_BUDGET_PROGRAM="ComputeBudget111111111111111111111111111111"
MAX_COMPUTE_UNITS=1_400_000
MAX_MICRO_LAMPORTS_PER_CU=1_000_000
DESTINATION_ROLES=("projectAdminTokenAccount","referralTokenAccount","partnerTokenAccount")


def strict_json(path):
    with Path(path).open("rb") as stream:raw=stream.read(MAX_JSON_BYTES+1)
    require(len(raw)<=MAX_JSON_BYTES,"JSON_TOO_LARGE")
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,"DUPLICATE_JSON_KEY");result[key]=value
        return result
    try:value=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    except ClaimV2AuditRejected:raise
    except Exception:raise ClaimV2AuditRejected("INVALID_JSON_INPUT") from None
    require(type(value) is dict,"INVALID_JSON_INPUT")
    return value


def audit_auxiliary_instructions(capture,binding):
    require(type(capture) is dict and type(binding) is dict,"INVALID_CAPTURE_CONTRACT")
    require(capture.get("status")=="SDK_UNSIGNED_CAPTURED"
            and capture.get("execution_ready") is False
            and capture.get("fee_receipt_verified") is False,"PINNED_CAPTURE_REQUIRED")
    require(binding.get("status")=="PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED"
            and binding.get("compiled_account_binding_verified") is True
            and binding.get("execution_ready") is False
            and binding.get("fee_receipt_verified") is False,"COMPILED_BINDING_REQUIRED")
    require(capture.get("message_sha256")==binding.get("message_sha256")
            and capture.get("transaction_sha256")==binding.get("transaction_sha256"),
            "CAPTURE_BINDING_HASH_MISMATCH")
    identity=capture.get("identity");accounts=dict(expected_accounts(identity))
    slot=capture.get("rpc_slot")
    require(type(slot) is int and slot>0,"INVALID_CAPTURE_SLOT")
    rebound=capture_claim_v2(capture.get("transaction"),identity,
                             {"context":{"slot":slot},"accounts":{}})
    require(rebound["message_sha256"]==capture["message_sha256"]
            and rebound["transaction_sha256"]==capture["transaction_sha256"],
            "CAPTURE_TRANSACTION_CHANGED")
    tx,_=_transaction(capture["transaction"])
    require(len(tx.message.address_table_lookups)==0,"LOOKUP_TABLE_NOT_ALLOWED")
    keys=[str(key) for key in tx.message.account_keys]
    decoded=[];claim_count=0;compute_limit=None;compute_price=None
    for index,instruction in enumerate(tx.message.instructions):
        require(instruction.program_id_index<len(keys),"PROGRAM_INDEX_OUT_OF_RANGE")
        require(all(account_index<len(keys) for account_index in instruction.accounts),
                "ACCOUNT_INDEX_OUT_OF_RANGE")
        program=keys[instruction.program_id_index]
        addresses=[keys[item] for item in instruction.accounts]
        data=bytes(instruction.data)
        if program==REFERRAL_PROGRAM:
            claim_count+=1
            require(index==len(tx.message.instructions)-1
                    and data.hex()==CLAIM_V2_DISCRIMINATOR,
                    "CLAIM_V2_MUST_BE_FINAL")
            decoded.append({"index":index,"kind":"CLAIM_V2","program":program,
                            "account_count":len(addresses),"data_hex":data.hex()})
            continue
        if index==0 and program==COMPUTE_BUDGET_PROGRAM:
            require(len(addresses)==0 and len(data)==5 and data[0]==2,
                    "COMPUTE_UNIT_LIMIT_MALFORMED")
            compute_limit=int.from_bytes(data[1:],"little")
            require(0<compute_limit<=MAX_COMPUTE_UNITS,"COMPUTE_UNIT_LIMIT_OUT_OF_RANGE")
            decoded.append({"index":index,"kind":"SET_COMPUTE_UNIT_LIMIT","program":program,
                            "account_count":0,"units":compute_limit,"data_hex":data.hex()})
            continue
        if index==1 and program==COMPUTE_BUDGET_PROGRAM:
            require(len(addresses)==0 and len(data)==9 and data[0]==3,
                    "COMPUTE_UNIT_PRICE_MALFORMED")
            compute_price=int.from_bytes(data[1:],"little")
            require(0<=compute_price<=MAX_MICRO_LAMPORTS_PER_CU,
                    "COMPUTE_UNIT_PRICE_OUT_OF_RANGE")
            decoded.append({"index":index,"kind":"SET_COMPUTE_UNIT_PRICE","program":program,
                            "account_count":0,"micro_lamports":compute_price,
                            "data_hex":data.hex()})
            continue
        require(index==2 and program==ASSOCIATED_TOKEN_PROGRAM,
                "AUXILIARY_PROGRAM_NOT_ALLOWED")
        require(data==b"","ATA_CREATE_DATA_MISMATCH")
        require(len(addresses)==6,"ATA_ACCOUNT_COUNT_MISMATCH")
        payer,destination,owner,mint,system_program,token_program=addresses
        require(payer==accounts["payer"] and mint==accounts["mint"]
                and system_program==SYSTEM_PROGRAM and token_program==TOKEN_PROGRAM,
                "ATA_FIXED_ACCOUNT_MISMATCH")
        require(destination==accounts["partnerTokenAccount"]
                and owner==accounts["partner"],"ATA_DESTINATION_OR_OWNER_MISMATCH")
        decoded.append({"index":index,"kind":"CREATE_PARTNER_ATA",
                        "program":program,"destination_role":"partnerTokenAccount",
                        "account_count":6,"data_hex":""})
    require(claim_count==1,"CLAIM_V2_INSTRUCTION_MISSING_OR_AMBIGUOUS")
    require(len(decoded)==4 and decoded[-1]["kind"]=="CLAIM_V2",
            "UNEXPECTED_INSTRUCTION_COUNT_OR_ORDER")
    require(compute_limit is not None and compute_price is not None,
            "COMPUTE_BUDGET_PAIR_REQUIRED")
    return {"status":"CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED",
        "message_sha256":capture["message_sha256"],
        "transaction_sha256":capture["transaction_sha256"],
        "instruction_count":len(decoded),"claim_instruction_index":3,
        "auxiliary_instruction_count":3,"decoded_instructions":decoded,
        "allowed_auxiliary_programs":[COMPUTE_BUDGET_PROGRAM,ASSOCIATED_TOKEN_PROGRAM],
        "compute_unit_limit":compute_limit,
        "compute_unit_price_micro_lamports":compute_price,
        "maximum_priority_fee_lamports":(compute_limit*compute_price+999_999)//1_000_000,
        "ata_create_destination":"partnerTokenAccount",
        "auxiliary_instruction_semantics_verified":True,
        "additional_signer_allowed":False,"free_transfer_allowed":False,
        "transaction_signed":False,"transaction_submitted":False,
        "claim_submitted":False,"controlled_live_swap_approved":False,
        "production_fee_execution_enabled":False,"execution_ready":False,
        "fee_receipt_verified":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture",required=True);parser.add_argument("--binding-report",required=True)
    parser.add_argument("--output",required=True);args=parser.parse_args(argv);output=Path(args.output)
    try:
        require(not output.exists(),"OUTPUT_ALREADY_EXISTS")
        report=audit_auxiliary_instructions(strict_json(args.capture),strict_json(args.binding_report))
        with output.open("x",encoding="utf-8") as stream:json.dump(report,stream,indent=2)
        print(json.dumps({key:report[key] for key in
            ("status","execution_ready","fee_receipt_verified")}));return 2
    except ClaimV2AuditRejected as error:reason=str(error)
    except Exception:reason="AUXILIARY_INPUT_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status":"CLAIM_V2_AUXILIARY_NOT_VERIFIED","reason":reason,
        "execution_ready":False,"fee_receipt_verified":False}));return 1


if __name__=="__main__":raise SystemExit(main())
