"""Read-only ClaimV2 simulation and exact token balance-delta semantics.

This operator harness never signs or submits a transaction. A successful
simulation remains review evidence and never authorizes a claim or live swap.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from solders.transaction import VersionedTransaction

from application.jupiter_claim_v2_auxiliary import audit_auxiliary_instructions
from application.jupiter_claim_v2_capture import capture_claim_v2, _transaction
from application.jupiter_claim_v2_semantics import (
    ACCOUNT_ORDER_AUTHORITY, PINNED_SDK_VERSION, ClaimV2AuditRejected,
    expected_accounts, require,
)
from application.jupiter_referral_verification import MAINNET_GENESIS, TOKEN_PROGRAM

MAX_JSON_BYTES = 524_288
MAX_RPC_BYTES = 524_288
MAX_UNITS = 1_400_000


def strict_json(raw, maximum=MAX_JSON_BYTES):
    require(type(raw) is bytes and len(raw) <= maximum, "JSON_TOO_LARGE")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except ClaimV2AuditRejected:
        raise
    except Exception:
        raise ClaimV2AuditRejected("INVALID_JSON_INPUT") from None
    require(type(value) is dict, "INVALID_JSON_INPUT")
    return value


def read_json(path):
    with Path(path).open("rb") as stream:
        return strict_json(stream.read(MAX_JSON_BYTES + 1))


def _endpoint(value):
    try:
        parsed = urlsplit(value)
        require(parsed.scheme == "https" and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not parsed.fragment, "HTTPS_RPC_CONFIGURATION_REQUIRED")
        _ = parsed.port
    except (TypeError, ValueError):
        raise ClaimV2AuditRejected("HTTPS_RPC_CONFIGURATION_REQUIRED") from None
    return value


def rpc(endpoint, method, params, request_post=None):
    require(method in {"getGenesisHash", "simulateTransaction"},
            "RPC_METHOD_NOT_ALLOWED")
    endpoint = _endpoint(endpoint)
    response = None
    try:
        import requests
        response = (request_post or requests.post)(endpoint,
            json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
            timeout=(3, 15), allow_redirects=False, stream=True)
        require(response.status_code == 200, "RPC_HTTP_ERROR")
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            raw.extend(chunk)
            require(len(raw) <= MAX_RPC_BYTES, "RPC_RESPONSE_TOO_LARGE")
        payload = strict_json(bytes(raw), MAX_RPC_BYTES)
        require(payload.get("jsonrpc") == "2.0" and payload.get("id") == 1
                and "result" in payload and "error" not in payload,
                "INVALID_RPC_ENVELOPE")
        return payload["result"]
    except ClaimV2AuditRejected:
        raise
    except Exception:
        raise ClaimV2AuditRejected("RPC_UNAVAILABLE") from None
    finally:
        if response is not None:
            response.close()


def raw_amount(value):
    require(type(value) is str and value.isdigit() and len(value) <= 40,
            "INVALID_TOKEN_AMOUNT")
    amount = int(value)
    require(0 <= amount < 2**64, "INVALID_TOKEN_AMOUNT")
    return amount


def token_amount(entries, index, mint, owner, *, allow_created_pre_zero=False):
    require(type(entries) is list and len(entries) <= 256,
            "INVALID_TOKEN_BALANCES")
    matches = [item for item in entries if type(item) is dict
               and item.get("accountIndex") == index]
    if not matches and allow_created_pre_zero:
        return 0, "CREATED_ATA_IMPLICIT_ZERO"
    require(len(matches) == 1, "CLAIM_TOKEN_BALANCE_MISSING_OR_AMBIGUOUS")
    item = matches[0]
    require(item.get("mint") == mint and item.get("owner") == owner
            and item.get("programId") == TOKEN_PROGRAM,
            "CLAIM_TOKEN_BALANCE_IDENTITY_MISMATCH")
    ui = item.get("uiTokenAmount")
    require(type(ui) is dict, "INVALID_TOKEN_AMOUNT")
    return raw_amount(ui.get("amount")), "RPC_TOKEN_BALANCE"


def validate_capture(capture, binding, auxiliary):
    require(type(capture) is dict and type(binding) is dict and type(auxiliary) is dict,
            "INVALID_CAPTURE_CONTRACT")
    require(capture.get("status") == "SDK_UNSIGNED_CAPTURED"
            and capture.get("sdk_version") == PINNED_SDK_VERSION
            and capture.get("execution_ready") is False
            and capture.get("fee_receipt_verified") is False,
            "PINNED_CAPTURE_REQUIRED")
    require(binding.get("status") == "PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED"
            and binding.get("compiled_account_binding_verified") is True
            and binding.get("execution_ready") is False
            and binding.get("fee_receipt_verified") is False,
            "COMPILED_BINDING_REQUIRED")
    require(capture.get("message_sha256") == binding.get("message_sha256")
            and capture.get("transaction_sha256") == binding.get("transaction_sha256"),
            "CAPTURE_BINDING_HASH_MISMATCH")
    require(auxiliary.get("status") == "CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED"
            and auxiliary.get("message_sha256") == capture.get("message_sha256")
            and auxiliary.get("transaction_sha256") == capture.get("transaction_sha256")
            and auxiliary.get("auxiliary_instruction_semantics_verified") is True
            and auxiliary.get("execution_ready") is False
            and auxiliary.get("fee_receipt_verified") is False,
            "AUXILIARY_ALLOWLIST_REPORT_REQUIRED")
    require(auxiliary.get("ata_create_destination") == "partnerTokenAccount",
            "PARTNER_ATA_CREATE_EVIDENCE_REQUIRED")
    independently_audited = audit_auxiliary_instructions(capture, binding)
    require(independently_audited["message_sha256"] == auxiliary["message_sha256"]
            and independently_audited["transaction_sha256"] == auxiliary["transaction_sha256"],
            "AUXILIARY_REPORT_REAUDIT_MISMATCH")
    identity = capture.get("identity")
    expected_accounts(identity)
    require(identity.get("referral_share_bps") == 8000,
            "REFERRAL_SHARE_REQUIRES_REVIEW")
    slot = capture.get("rpc_slot")
    require(type(slot) is int and slot > 0, "INVALID_CAPTURE_SLOT")
    rebound = capture_claim_v2(capture.get("transaction"), identity,
                               {"context":{"slot":slot},"accounts":{}})
    require(rebound["message_sha256"] == capture["message_sha256"]
            and rebound["transaction_sha256"] == capture["transaction_sha256"],
            "CAPTURE_TRANSACTION_CHANGED")
    return identity, slot, rebound


def audit_claim_simulation(capture, binding, auxiliary, *, environment=None, request_post=None):
    env = os.environ if environment is None else environment
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower() == "false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    identity, slot, rebound = validate_capture(capture, binding, auxiliary)
    endpoint = env.get("SOLANA_RPC_URL", "")
    require(rpc(endpoint, "getGenesisHash", [], request_post) == MAINNET_GENESIS,
            "RPC_IS_NOT_SOLANA_MAINNET")
    tx, _ = _transaction(capture["transaction"])
    keys = [str(key) for key in tx.message.account_keys]
    addresses = dict(expected_accounts(identity))
    role_indexes = {}
    for role in ("projectAdminTokenAccount", "referralTokenAccount", "partnerTokenAccount"):
        matches = [index for index, key in enumerate(keys) if key == addresses[role]]
        require(len(matches) == 1, "CLAIM_TOKEN_ACCOUNT_INDEX_AMBIGUOUS")
        role_indexes[role] = matches[0]
    config = {"encoding":"base64","commitment":"confirmed","sigVerify":False,
              "replaceRecentBlockhash":True,"minContextSlot":slot,
              "innerInstructions":True,
              "accounts":{"encoding":"base64","addresses":[
                  addresses["referralTokenAccount"],
                  addresses["partnerTokenAccount"],
                  addresses["projectAdminTokenAccount"],
              ]}}
    simulated = rpc(endpoint, "simulateTransaction",
                    [capture["transaction"], config], request_post)
    require(type(simulated) is dict and type(simulated.get("context")) is dict
            and type(simulated.get("value")) is dict,
            "INVALID_SIMULATION_RESULT")
    simulation_slot = simulated["context"].get("slot")
    value = simulated["value"]
    require(type(simulation_slot) is int and simulation_slot >= slot,
            "SIMULATION_SLOT_MISMATCH")
    require(value.get("err") is None, "CLAIM_V2_SIMULATION_FAILED")
    units = value.get("unitsConsumed")
    require(type(units) is int and 0 < units <= MAX_UNITS,
            "INVALID_SIMULATION_UNITS")
    pre_balances = value.get("preTokenBalances")
    post_balances = value.get("postTokenBalances")
    mint = identity["mint"]
    observations = {}
    for role, owner in (("referralTokenAccount", identity["referral_account"]),
                        ("partnerTokenAccount", identity["partner"]),
                        ("projectAdminTokenAccount", identity["admin"])):
        index = role_indexes[role]
        pre,pre_source = token_amount(pre_balances,index,mint,owner,
            allow_created_pre_zero=role=="partnerTokenAccount")
        post,post_source = token_amount(post_balances,index,mint,owner)
        observations[role] = (pre,post,pre_source,post_source)
    referral_pre,referral_post,referral_pre_source,_ = observations["referralTokenAccount"]
    partner_pre,partner_post,partner_pre_source,_ = observations["partnerTokenAccount"]
    admin_pre,admin_post,admin_pre_source,_ = observations["projectAdminTokenAccount"]
    require(referral_pre > 0 and referral_post <= referral_pre,
            "REFERRAL_SOURCE_DELTA_INVALID")
    gross = referral_pre - referral_post
    partner_delta = partner_post - partner_pre
    admin_delta = admin_post - admin_pre
    require(partner_delta >= 0 and admin_delta >= 0,
            "CLAIM_DESTINATION_DELTA_INVALID")
    expected_partner = gross * 8000 // 10_000
    expected_admin = gross - expected_partner
    require(partner_delta == expected_partner,
            "PARTNER_CLAIM_DELTA_MISMATCH")
    require(admin_delta == expected_admin,
            "PROJECT_ADMIN_CLAIM_DELTA_MISMATCH")
    require(gross == partner_delta + admin_delta,
            "CLAIM_BALANCE_CONSERVATION_MISMATCH")
    logs = value.get("logs")
    require(type(logs) is list and len(logs) <= 512
            and all(type(line) is str and len(line) <= 1024 for line in logs),
            "INVALID_SIMULATION_LOGS")
    return {
        "status":"CLAIM_V2_SIMULATION_BALANCE_DELTA_REVIEW_REQUIRED",
        "simulation_only":True,
        "transaction_signed":False,
        "transaction_submitted":False,
        "claim_submitted":False,
        "controlled_live_swap_approved":False,
        "production_fee_execution_enabled":False,
        "execution_ready":False,
        "fee_receipt_verified":False,
        "on_chain_receipt_verified":False,
        "message_sha256":capture["message_sha256"],
        "capture_slot":slot,
        "simulation_slot":simulation_slot,
        "sdk_version":PINNED_SDK_VERSION,
        "account_order_authority":ACCOUNT_ORDER_AUTHORITY,
        "mint":mint,
        "referral_share_bps":8000,
        "project_share_bps":2000,
        "referral_pre_raw":str(referral_pre),
        "referral_post_raw":str(referral_post),
        "gross_claim_raw":str(gross),
        "partner_pre_raw":str(partner_pre),
        "partner_pre_source":partner_pre_source,
        "partner_post_raw":str(partner_post),
        "partner_delta_raw":str(partner_delta),
        "project_admin_pre_raw":str(admin_pre),
        "project_admin_post_raw":str(admin_post),
        "project_admin_delta_raw":str(admin_delta),
        "referral_pre_source":referral_pre_source,
        "project_admin_pre_source":admin_pre_source,
        "simulated_claim_split_verified":True,
        "balance_conservation_verified":True,
        "compiled_binding_status":rebound["status"],
        "units_consumed":units,
        "inner_instructions_observed":type(value.get("innerInstructions")) is list,
        "log_count":len(logs),
        "note":"Read-only simulation evidence is not an on-chain claim receipt or execution approval.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--binding-report", required=True)
    parser.add_argument("--auxiliary-report", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    destination = Path(args.output_dir)
    try:
        require(not destination.exists(), "OUTPUT_ALREADY_EXISTS")
        report = audit_claim_simulation(read_json(args.capture),
            read_json(args.binding_report), read_json(args.auxiliary_report))
        destination.mkdir(parents=False)
        with (destination / "claim_v2_simulation_report.json").open(
                "x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps({key:report[key] for key in
            ("status", "execution_ready", "fee_receipt_verified")}))
        return 2
    except ClaimV2AuditRejected as error:
        reason = str(error)
    except Exception:
        reason = "CLAIM_SIMULATION_INPUT_CONFIGURATION_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status":"CLAIM_V2_SIMULATION_NOT_VERIFIED",
        "reason":reason,"execution_ready":False,"fee_receipt_verified":False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
