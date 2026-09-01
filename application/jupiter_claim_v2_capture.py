"""Offline unsigned ClaimV2 capture and compiled-account binding.

Consumes exported transaction bytes and a supplied ALT snapshot. It performs no
network request and cannot build, sign, simulate, submit or claim a transaction.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path

from solders.message import to_bytes_versioned
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from application.jupiter_claim_v2_semantics import (
    ACCOUNT_ROLES, CLAIM_V2_DISCRIMINATOR, REFERRAL_PROGRAM,
    ClaimV2AuditRejected, audit_claim_v2_instruction, require,
)
from application.jupiter_order_identity_binding import U64_MAX, resolve_keys

MAX_TRANSACTION_BYTES = 1232
MAX_INPUT_BYTES = 262_144


def _strict_json(path):
    with Path(path).open("rb") as stream:
        raw=stream.read(MAX_INPUT_BYTES+1)
    require(len(raw)<=MAX_INPUT_BYTES,"CAPTURE_INPUT_TOO_LARGE")
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,"DUPLICATE_JSON_KEY")
            result[key]=value
        return result
    try:
        value=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=unique,
                         parse_constant=lambda _ : (_ for _ in ()).throw(ValueError()))
    except ClaimV2AuditRejected:
        raise
    except Exception:
        raise ClaimV2AuditRejected("INVALID_CAPTURE_JSON") from None
    require(type(value) is dict,"INVALID_CAPTURE_JSON")
    return value


def _transaction(encoded):
    require(type(encoded) is str and len(encoded)<=2048,"INVALID_UNSIGNED_TRANSACTION")
    try:
        raw=base64.b64decode(encoded,validate=True)
        require(base64.b64encode(raw).decode()==encoded,"NONCANONICAL_TRANSACTION_ENCODING")
        require(0<len(raw)<=MAX_TRANSACTION_BYTES,"TRANSACTION_SIZE_LIMIT")
        tx=VersionedTransaction.from_bytes(raw)
    except ClaimV2AuditRejected:
        raise
    except (ValueError,TypeError,binascii.Error):
        raise ClaimV2AuditRejected("INVALID_UNSIGNED_TRANSACTION") from None
    require(bytes(tx)==raw,"NONCANONICAL_TRANSACTION_BYTES")
    return tx,raw


def capture_claim_v2(encoded,identity,snapshot):
    require(type(snapshot) is dict and set(snapshot)=={"context","accounts"},
            "INVALID_LOOKUP_SNAPSHOT")
    context=snapshot["context"]
    slot=context.get("slot") if type(context) is dict else None
    require(type(slot) is int and 0<slot<=U64_MAX,"INVALID_SNAPSHOT_SLOT")
    accounts=snapshot["accounts"]
    require(type(accounts) is dict and len(accounts)<=8,"INVALID_LOOKUP_SNAPSHOT")
    tx,raw=_transaction(encoded)
    header=tx.message.header
    require(header.num_required_signatures==1 and len(tx.signatures)==1,
            "UNEXPECTED_TRANSACTION_SIGNER_COUNT")
    require(tx.signatures[0]==Signature.default(),"TRANSACTION_IS_ALREADY_SIGNED")
    metas,lookup_hashes=resolve_keys(tx.message,accounts,slot)
    require(metas and metas[0]==(identity.get("payer"),True,True),
            "CLAIM_PAYER_BINDING_MISMATCH")
    matches=[]
    referral_instruction_count=0
    for index,instruction in enumerate(tx.message.instructions):
        require(instruction.program_id_index<len(metas),"PROGRAM_INDEX_OUT_OF_RANGE")
        program=metas[instruction.program_id_index][0]
        if program==REFERRAL_PROGRAM:
            referral_instruction_count+=1
        data=bytes(instruction.data)
        if program==REFERRAL_PROGRAM and data[:8].hex()==CLAIM_V2_DISCRIMINATOR:
            matches.append((index,instruction,data))
    require(len(matches)==1,"CLAIM_V2_INSTRUCTION_MISSING_OR_AMBIGUOUS")
    index,instruction,data=matches[0]
    require(len(data)==8,"CLAIM_V2_ARGUMENTS_UNEXPECTED")
    require(len(instruction.accounts)==len(ACCOUNT_ROLES),
            "CLAIM_V2_ACCOUNT_COUNT_MISMATCH")
    # Repeated indexes are valid when the permissionless payer is also partner;
    # the E.4A role/address contract decides which aliases are permitted.
    require(all(account_index<len(metas) for account_index in instruction.accounts),
            "ACCOUNT_INDEX_OUT_OF_RANGE")
    normalized=[]
    for role,account_index in zip(ACCOUNT_ROLES,instruction.accounts):
        address,signer,writable=metas[account_index]
        normalized.append({"role":role,"address":address,"signer":signer,
                           "writable":writable})
    semantic=audit_claim_v2_instruction({"program":REFERRAL_PROGRAM,
        "discriminator":CLAIM_V2_DISCRIMINATOR,"accounts":normalized},identity)
    message_bytes=to_bytes_versioned(tx.message)
    return {
        "status":"UNSIGNED_CLAIM_V2_ACCOUNT_BINDING_REVIEW_REQUIRED",
        "transaction_sha256":hashlib.sha256(raw).hexdigest(),
        "message_sha256":hashlib.sha256(message_bytes).hexdigest(),
        "transaction_size_bytes":len(raw),
        "snapshot_slot":slot,
        "claim_instruction_index":index,
        "instruction_count":len(tx.message.instructions),
        "referral_instruction_count":referral_instruction_count,
        "auxiliary_instructions_present":len(tx.message.instructions)>1,
        "lookup_table_count":len(tx.message.address_table_lookups),
        "lookup_account_data_sha256":lookup_hashes,
        "compiled_account_binding_verified":True,
        "source_semantics_status":semantic["status"],
        "source_commit":semantic["source_commit"],
        "account_roles":semantic["account_roles"],
        "snapshot_authenticity_verified":False,
        "snapshot_freshness_verified":False,
        "auxiliary_instruction_semantics_verified":len(tx.message.instructions)==1,
        "deployed_program_binary_verified":False,
        "claim_transaction_simulated":False,
        "claim_split_verified":False,
        "claim_submitted":False,
        "controlled_live_swap_approved":False,
        "production_fee_execution_enabled":False,
        "execution_ready":False,
        "fee_receipt_verified":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args(argv)
    destination=Path(args.output)
    try:
        require(not destination.exists(),"OUTPUT_ALREADY_EXISTS")
        payload=_strict_json(args.input)
        require(set(payload)=={"transaction","identity","lookup_snapshot"},
                "INVALID_CAPTURE_FIELDS")
        report=capture_claim_v2(payload["transaction"],payload["identity"],
                                payload["lookup_snapshot"])
        with destination.open("x",encoding="utf-8") as stream:
            json.dump(report,stream,indent=2)
        print(json.dumps({k:report[k] for k in
            ("status","execution_ready","fee_receipt_verified")}))
        return 2
    except ClaimV2AuditRejected as error:
        print(json.dumps({"status":"UNSIGNED_CLAIM_V2_NOT_VERIFIED",
            "reason":str(error),"execution_ready":False,
            "fee_receipt_verified":False}))
        return 1
    except Exception:
        print(json.dumps({"status":"UNSIGNED_CLAIM_V2_NOT_VERIFIED",
            "reason":"CAPTURE_INPUT_OR_OUTPUT_UNAVAILABLE","execution_ready":False,
            "fee_receipt_verified":False}))
        return 1


if __name__=="__main__":raise SystemExit(main())
