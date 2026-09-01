"""Fresh fee-bearing order simulation and referral balance-delta evidence.

Operator-only: never signs, sends, executes or mutates production fee settings.
Simulation is not an on-chain receipt and never authorizes execution.
"""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from solders.transaction import VersionedTransaction

from application.jupiter_ata_lifecycle_binding import audit_ata_lifecycle
from application.jupiter_fee_policy import WSOL_MINT, read_fee_policy, validate_fee_response
from application.jupiter_minimum_contract import MinimumContractRejected, raw_uint, require
from application.jupiter_order_identity_binding import audit_order_identity, resolve_keys
from application.jupiter_referral_verification import (
    MAINNET_GENESIS, TOKEN_PROGRAM, referral_token_address, verify_referral_accounts,
)

MAX_INPUT = 1_000_000
MAX_RPC = 524_288
MAX_AGE_SECONDS = 300


def strict_json(raw, maximum=MAX_RPC):
    require(len(raw) <= maximum, "JSON_TOO_LARGE")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except MinimumContractRejected:
        raise
    except Exception:
        raise MinimumContractRejected("INVALID_JSON") from None
    require(type(value) is dict, "INVALID_JSON_OBJECT")
    return value


def read_file(path, maximum=MAX_RPC):
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    return strict_json(raw, maximum)


def recent(value, now):
    require(type(value) is str and len(value) <= 64, "MISSING_EVIDENCE_TIMESTAMP")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(stamp.tzinfo is not None, "MISSING_EVIDENCE_TIMESTAMP")
    except (ValueError, TypeError):
        raise MinimumContractRejected("MISSING_EVIDENCE_TIMESTAMP") from None
    age = (now - stamp.astimezone(timezone.utc)).total_seconds()
    require(0 <= age <= MAX_AGE_SECONDS, "EVIDENCE_NOT_FRESH")
    return age


def rpc(endpoint, method, params, request_post=None):
    require(method in {"getGenesisHash", "simulateTransaction"}, "RPC_METHOD_NOT_ALLOWED")
    try:
        url = urlsplit(endpoint)
        require(url.scheme == "https" and bool(url.hostname) and not url.username
                and not url.password and not url.fragment, "HTTPS_RPC_CONFIGURATION_REQUIRED")
        _ = url.port
    except (ValueError, TypeError):
        raise MinimumContractRejected("HTTPS_RPC_CONFIGURATION_REQUIRED") from None
    response = None
    try:
        import requests
        response = (request_post or requests.post)(endpoint,
            json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
            timeout=(3,15), allow_redirects=False, stream=True)
        require(response.status_code == 200, "RPC_HTTP_ERROR")
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            raw.extend(chunk); require(len(raw) <= MAX_RPC, "RPC_RESPONSE_TOO_LARGE")
        payload = strict_json(bytes(raw))
        require(payload.get("jsonrpc") == "2.0" and payload.get("id") == 1
                and "result" in payload and "error" not in payload, "INVALID_RPC_ENVELOPE")
        return payload["result"]
    except MinimumContractRejected:
        raise
    except Exception:
        raise MinimumContractRejected("RPC_UNAVAILABLE") from None
    finally:
        if response is not None: response.close()


def token_balance(entries, account_index, mint, owner):
    require(type(entries) is list and len(entries) <= 256, "INVALID_TOKEN_BALANCES")
    matches = [item for item in entries if type(item) is dict
               and item.get("accountIndex") == account_index]
    require(len(matches) == 1, "REFERRAL_TOKEN_BALANCE_MISSING_OR_AMBIGUOUS")
    item = matches[0]
    require(item.get("mint") == mint and item.get("owner") == owner
            and item.get("programId") == TOKEN_PROGRAM, "REFERRAL_TOKEN_IDENTITY_MISMATCH")
    amount = item.get("uiTokenAmount", {}).get("amount")
    return raw_uint(amount)


def audit_simulation(evidence, capture, live, snapshot, intent, *, environment=None,
                     request_post=None, now=None):
    env = os.environ if environment is None else environment
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower() == "false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    current = now or datetime.now(timezone.utc)
    capture_age = recent(capture.get("captured_at"), current)
    live_age = recent(live.get("checked_at"), current)
    require(type(evidence.get("order")) is dict and type(evidence.get("quote")) is dict,
            "INVALID_EVIDENCE")
    order = evidence["order"]
    require(order.get("inputMint") == WSOL_MINT and raw_uint(order.get("inAmount")) == MAX_INPUT,
            "CONTROLLED_INPUT_REQUIRED")
    policy = read_fee_policy({"DEXSATO_JUPITER_FEE_ENABLED":"true",
        "DEXSATO_JUPITER_REFERRAL_ACCOUNT":env.get("DEXSATO_JUPITER_REFERRAL_ACCOUNT", ""),
        "DEXSATO_JUPITER_REFERRAL_FEE_BPS":"50"})
    fee = validate_fee_response(policy, order, input_mint=order["inputMint"],
                                output_mint=order.get("outputMint"))
    require(fee.fee_mint == WSOL_MINT and order.get("referralAccount") == policy.referral_account,
            "FEE_DESTINATION_POLICY_MISMATCH")
    platform = order.get("platformFee")
    require(type(platform) is dict and platform.get("feeBps") == 50
            and platform.get("feeMint") == WSOL_MINT,
            "PLATFORM_FEE_EVIDENCE_MISSING")
    total_fee = MAX_INPUT * 50 // 10_000
    provider_amount = platform.get("amount")
    if provider_amount is not None:
        require(raw_uint(provider_amount) == total_fee, "PLATFORM_FEE_AMOUNT_MISMATCH")
    expected_partner_claim = total_fee * 8_000 // 10_000
    require(type(intent) is dict and intent.get("message_sha256") == capture.get("message_sha256")
            == live.get("message_sha256"), "MESSAGE_HASH_EVIDENCE_MISMATCH")
    require(live.get("status") == "LIVE_IDENTITY_REVIEW_REQUIRED"
            and live.get("identity_snapshot_consistent") is True
            and live.get("execution_ready") is False
            and live.get("ata_lifecycle", {}).get("lifecycle_instruction_order_verified") is True,
            "LIVE_IDENTITY_EVIDENCE_NOT_VERIFIED")
    slot = live.get("slot")
    lifecycle = audit_ata_lifecycle(order.get("transaction"), order, intent, snapshot,
                                    intent["message_sha256"], slot)
    binding = audit_order_identity(order["transaction"], order, intent, snapshot,
        intent["message_sha256"], slot,
        precreated_token_accounts=set(lifecycle["missing_prestate_accounts"]))
    referral = verify_referral_accounts(policy.referral_account,
        env.get("DEXSATO_JUPITER_REFERRAL_PARTNER", ""),
        rpc_url=env.get("SOLANA_RPC_URL", ""), request_post=request_post)
    require(referral.partner_share_bps == 8000, "REFERRAL_SHARE_MISMATCH")
    referral_ata = referral_token_address(policy.referral_account, WSOL_MINT)
    tx = VersionedTransaction.from_bytes(base64.b64decode(order["transaction"], validate=True))
    metas, _ = resolve_keys(tx.message, snapshot["accounts"], slot)
    indexes = [i for i, meta in enumerate(metas) if meta[0] == referral_ata]
    require(len(indexes) == 1 and metas[indexes[0]][2] and not metas[indexes[0]][1],
            "REFERRAL_ATA_NOT_WRITABLE_OR_AMBIGUOUS")
    endpoint = env.get("SOLANA_RPC_URL", "")
    require(rpc(endpoint,"getGenesisHash",[],request_post) == MAINNET_GENESIS,
            "RPC_IS_NOT_SOLANA_MAINNET")
    config = {"encoding":"base64","commitment":"confirmed","sigVerify":False,
              "replaceRecentBlockhash":True,"minContextSlot":slot,
              "innerInstructions":True,
              "accounts":{"encoding":"base64","addresses":[referral_ata]}}
    simulated = rpc(endpoint,"simulateTransaction",
                    [order["transaction"],config],request_post)
    require(type(simulated) is dict and type(simulated.get("context")) is dict
            and type(simulated.get("value")) is dict, "INVALID_SIMULATION_RESULT")
    value = simulated["value"]
    require(type(simulated["context"].get("slot")) is int
            and simulated["context"]["slot"] >= slot, "SIMULATION_SLOT_MISMATCH")
    require(value.get("err") is None, "SIMULATION_FAILED")
    require(type(value.get("unitsConsumed")) is int and 0 < value["unitsConsumed"] <= 1_400_000,
            "INVALID_SIMULATION_UNITS")
    pre = token_balance(value.get("preTokenBalances"), indexes[0], WSOL_MINT,
                        policy.referral_account)
    post = token_balance(value.get("postTokenBalances"), indexes[0], WSOL_MINT,
                         policy.referral_account)
    require(post >= pre and post - pre == total_fee, "REFERRAL_BALANCE_DELTA_MISMATCH")
    logs = value.get("logs")
    require(type(logs) is list and len(logs) <= 512
            and all(type(line) is str and len(line) <= 1024 for line in logs),
            "INVALID_SIMULATION_LOGS")
    return {"status":"SIMULATED_GROSS_REFERRAL_ACCRUAL_REVIEW_REQUIRED",
            "execution_ready":False,"fee_receipt_verified":False,
            "transaction_submitted":False,"simulation_only":True,
            "production_fee_execution_enabled":False,
            "message_sha256":intent["message_sha256"],
            "capture_age_seconds":capture_age,"live_snapshot_age_seconds":live_age,
            "simulation_slot":simulated["context"]["slot"],
            "fee_mint":WSOL_MINT,"provider_fee_bps":50,
            "platform_fee_raw":str(total_fee),"partner_share_bps":8000,
            "provider_platform_fee_amount_present":provider_amount is not None,
            "platform_fee_source":"DETERMINISTIC_INPUT_BPS_ARITHMETIC",
            "expected_referral_accrual_delta_raw":str(total_fee),
            "expected_partner_claim_raw":str(expected_partner_claim),
            "referral_pre_raw":str(pre),"referral_post_raw":str(post),
            "referral_delta_raw":str(post-pre),
            "simulation_gross_referral_accrual_verified":True,
            "partner_claim_delta_observed":False,
            "claim_split_verified":False,
            "on_chain_receipt_verified":False,
            "units_consumed":value["unitsConsumed"],
            "inner_instructions_observed":type(value.get("innerInstructions")) is list,
            "log_count":len(logs),
            "identity_binding_status":binding["status"],
            "ata_lifecycle_status":lifecycle["status"],
            "note":"Simulation verifies gross referral accrual only. Partner/Jupiter claim split is not executed or verified."}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("evidence","capture-report","live-report","live-snapshot","intent"):
        parser.add_argument("--"+name,required=True)
    parser.add_argument("--output-dir",required=True)
    args=parser.parse_args(argv)
    destination=Path(args.output_dir)
    try:
        destination.mkdir(parents=False,exist_ok=False)
        report=audit_simulation(read_file(args.evidence),read_file(args.capture_report),
            read_file(args.live_report),read_file(args.live_snapshot),read_file(args.intent))
        with (destination/"fee_balance_simulation_report.json").open("x",encoding="utf-8") as stream:
            json.dump(report,stream,indent=2)
        print(json.dumps({k:report[k] for k in ("status","execution_ready","fee_receipt_verified")}))
        return 2
    except MinimumContractRejected as error: reason=str(error)
    except Exception: reason="SIMULATION_INPUT_CONFIGURATION_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status":"SIMULATION_NOT_VERIFIED","reason":reason,
                      "execution_ready":False,"fee_receipt_verified":False}))
    return 1


if __name__=="__main__": raise SystemExit(main())
