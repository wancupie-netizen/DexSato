"""Operator-only unsigned simulation. Reports are NEVER execution authorization."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from application.jupiter_lookup_decoder import inspect_resolved, message_layout, DecodeRejected
from application.jupiter_fee_transaction_harness import load_evidence, amount
from application.jupiter_fee_policy import WSOL_MINT, USDC_MINT, read_fee_policy, validate_fee_response
from application.jupiter_referral_verification import (
    verify_referral_accounts, _pubkey, TOKEN_PROGRAM, ASSOCIATED_TOKEN_PROGRAM,
)
from application.jupiter_swap_service import _base58_text
from application.jupiter_inner_evidence import capture_inner, claim_projection

SYSTEM = "11111111111111111111111111111111"
COMPUTE = "ComputeBudget111111111111111111111111111111"


class SimulationRejected(ValueError):
    pass


def require(condition, code):
    if not condition: raise SimulationRejected(code)


def ata(owner, mint):
    key = _pubkey(owner)
    return str(type(key).find_program_address([bytes(key), bytes(_pubkey(TOKEN_PROGRAM)),
        bytes(_pubkey(mint))], _pubkey(ASSOCIATED_TOKEN_PROGRAM))[0])


def validate_profile(evidence, resolved, wallet, referral, fee_ata, input_raw, minimum, fee_bps):
    """Narrow reviewed WSOL->USDC V2 profile; unknown top-level behavior rejects."""
    policy = read_fee_policy({"DEXSATO_JUPITER_FEE_ENABLED": "true",
        "DEXSATO_JUPITER_REFERRAL_ACCOUNT": referral, "DEXSATO_JUPITER_REFERRAL_FEE_BPS": str(fee_bps)})
    for payload in (evidence["quote"], evidence["order"]):
        require(payload.get("inputMint") == WSOL_MINT and payload.get("outputMint") == USDC_MINT
            and payload.get("inAmount") == input_raw and payload.get("swapMode") == "ExactIn"
            and payload.get("router") == "metis", "INTENT_MISMATCH")
        require(amount(minimum) <= amount(payload.get("otherAmountThreshold")) <= amount(payload.get("outAmount")), "OUTPUT_BOUND_MISMATCH")
        validate_fee_response(policy, payload, input_mint=WSOL_MINT, output_mint=USDC_MINT)
    order = evidence["order"]
    require(evidence["quote"].get("transaction") in (None, "") and order.get("taker") == wallet
        and order.get("gasless") is False and order.get("signatureFeePayer") == wallet, "WALLET_OR_PAYER_MISMATCH")
    require([a["address"] for a in resolved["accounts"] if a["is_signer"]] == [wallet], "SIGNER_MISMATCH")
    ixs = resolved["instructions"]
    routes = [ix for ix in ixs if ix.get("name") == "sharedAccountsRouteV2"]
    require(len(routes) == 1, "ONE_REVIEWED_V2_ROUTE_REQUIRED")
    route = routes[0]; args = route["args"]; roles = route["accounts"]
    require(args["inAmount"] == amount(input_raw) and args["quotedOutAmount"] == amount(order["outAmount"])
        and args["platformFeeBps"] == fee_bps and args["positiveSlippageBps"] == 0
        and type(order.get("slippageBps")) is int and args["slippageBps"] == order["slippageBps"]
        and 0 <= args["slippageBps"] <= 100, "V2_HEADER_MISMATCH")
    source, destination = ata(wallet, WSOL_MINT), ata(wallet, USDC_MINT)
    for role, expected in {"userTransferAuthority": wallet, "sourceMint": WSOL_MINT,
        "destinationMint": USDC_MINT, "sourceTokenAccount": source, "destinationTokenAccount": destination,
        "sourceTokenProgram": TOKEN_PROGRAM, "destinationTokenProgram": TOKEN_PROGRAM}.items():
        require(roles[role]["address"] == expected, "V2_ACCOUNT_ROLE_MISMATCH")
    remaining = route["remaining_accounts"]
    require(bool(remaining) and remaining[0]["address"] == fee_ata and remaining[0]["is_writable"], "EXPECTED_FEE_ATA_POSITION_MISMATCH")
    # Position is observed-profile evidence, NOT a generic proof of V2 recipient semantics.
    transfers = 0; seen = set()
    for ix in ixs:
        if ix is route: continue
        program = ix["program"]; data = bytes.fromhex(ix["data_hex"])
        accounts = [a["address"] for a in ix["instruction_accounts"]]
        if program == COMPUTE:
            require(ix["index"] < route["index"] and not accounts and data[:1] in (b"\2", b"\3"), "COMPUTE_PROFILE_MISMATCH")
            tag = data[0]; require(tag not in seen, "DUPLICATE_COMPUTE_SETTING"); seen.add(tag)
            require(len(data) == (5 if tag == 2 else 9), "COMPUTE_ENCODING_MISMATCH")
            value = int.from_bytes(data[1:], "little")
            require(value <= (1400000 if tag == 2 else 1000000), "COMPUTE_BUDGET_OUT_OF_BOUNDS")
        elif program == ASSOCIATED_TOKEN_PROGRAM:
            require(ix["index"] < route["index"] and data == b"\1" and accounts in
                ([wallet, source, wallet, WSOL_MINT, SYSTEM, TOKEN_PROGRAM],
                 [wallet, destination, wallet, USDC_MINT, SYSTEM, TOKEN_PROGRAM]), "ATA_PROFILE_MISMATCH")
        elif program == SYSTEM:
            require(ix["index"] < route["index"] and len(data) == 12 and data[:4] == b"\2\0\0\0"
                and accounts == [wallet, source], "SYSTEM_TRANSFER_PROFILE_MISMATCH")
            transfers += int.from_bytes(data[4:], "little")
        elif program == TOKEN_PROGRAM:
            require((data == b"\x11" and accounts == [source] and ix["index"] < route["index"])
                or (data == b"\x09" and accounts == [source, wallet, wallet] and ix["index"] > route["index"]), "TOKEN_PROFILE_MISMATCH")
        else: raise SimulationRejected("UNREVIEWED_TOP_LEVEL_PROGRAM")
    require(transfers == amount(input_raw), "TOTAL_SOL_TRANSFER_MISMATCH")
    return {"route_index": route["index"], "source": source, "destination": destination,
        "fee_ata": fee_ata, "input_raw": input_raw, "fee_bps": fee_bps,
        "gross_fee_arithmetic_raw": amount(input_raw) * fee_bps // 10000,
        "note": "Arithmetic reference only; actual split/rounding requires program/CPI evidence."}


def simulate_rpc(url, transaction, slot, addresses, request_post=None):
    """Fixed simulateTransaction only; no sendTransaction method or fallback."""
    message_layout(transaction)  # Refuse signed/malformed material even via direct calls.
    parsed = urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment, "HTTPS_RPC_CONFIGURATION_REQUIRED")
    if request_post is None:
        import requests
        request_post = requests.post
    response = None
    try:
        response = request_post(url, json={"jsonrpc": "2.0", "id": 1, "method": "simulateTransaction",
            "params": [transaction, {"encoding": "base64", "commitment": "finalized",
                "sigVerify": False, "replaceRecentBlockhash": True, "innerInstructions": True,
                "minContextSlot": slot, "accounts": {"encoding": "base64", "addresses": addresses}}]},
            timeout=(3, 30), stream=True, allow_redirects=False)
        require(response.status_code == 200, "SIMULATION_RPC_HTTP_ERROR")
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            raw.extend(chunk); require(len(raw) <= 1048576, "SIMULATION_RESPONSE_TOO_LARGE")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, "DUPLICATE_RPC_JSON_KEY"); result[key] = value
            return result
        payload = json.loads(raw, object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(SimulationRejected("INVALID_RPC_NUMBER")))
        require(isinstance(payload, dict) and payload.get("jsonrpc") == "2.0" and type(payload.get("id")) is int
            and payload["id"] == 1 and "error" not in payload and "result" in payload, "SIMULATION_RPC_ENVELOPE_ERROR")
        return payload["result"]
    except SimulationRejected: raise
    except Exception: raise SimulationRejected("SIMULATION_RPC_UNAVAILABLE") from None
    finally:
        if response is not None: response.close()


def token_state(account, mint, authority):
    require(isinstance(account, dict) and account.get("owner") == TOKEN_PROGRAM and account.get("executable") is False, "POST_TOKEN_OWNER_MISMATCH")
    data = account.get("data")
    require(isinstance(data, list) and len(data) == 2 and data[1] == "base64" and isinstance(data[0], str) and len(data[0]) <= 300, "POST_TOKEN_ENCODING_MISMATCH")
    raw = base64.b64decode(data[0], validate=True)
    require(len(raw) == 165 and _base58_text(raw[:32]) == mint and _base58_text(raw[32:64]) == authority
        and raw[108] == 1 and raw[72:76] == bytes(4) and raw[129:133] == bytes(4), "POST_TOKEN_STATE_MISMATCH")
    return {"mint": mint, "authority": authority, "amount_raw": str(int.from_bytes(raw[64:72], "little"))}


def summarize_simulation(result, resolved, profile, wallet, referral, minimum, minimum_slot):
    require(isinstance(result, dict) and isinstance(result.get("context"), dict) and isinstance(result.get("value"), dict), "INVALID_SIMULATION_RESULT")
    slot = result["context"].get("slot"); value = result["value"]
    require(type(slot) is int and slot >= minimum_slot and "err" in value, "INVALID_SIMULATION_SLOT_OR_ERROR")
    report = {"status": "SIMULATION_REVIEW_REQUIRED", "execution_ready": False, "fee_receipt_verified": False,
        "transaction_fee_verified": False, "message_sha256": resolved["message_sha256"],
        "simulation_slot": slot, "signature_verification": False, "blockhash_replaced": True,
        "profile": profile, "simulation_succeeded": value["err"] is None,
        "note": "Unsigned hypothetical execution, not wallet approval or on-chain receipt. No before/after balance delta is inferred across different slots."}
    try:
        report['inner_instruction_evidence'] = capture_inner(value, len(resolved['instructions']))
    except ValueError:
        raise SimulationRejected('INVALID_INNER_EVIDENCE') from None
    report['resolved_message_accounts'] = resolved['accounts']
    report['lookup_context'] = resolved['lookup_context']
    if value["err"] is not None:
        report.update(status="SIMULATION_FAILED", reason="RPC_SIMULATION_RETURNED_ERROR")
        # Safe numeric instruction/custom code only, not raw provider text/logs.
        err = value["err"]
        entry = err.get("InstructionError") if isinstance(err, dict) else None
        if isinstance(entry, list) and len(entry) == 2 and type(entry[0]) is int:
            report["failed_instruction_index"] = entry[0]
            if isinstance(entry[1], dict) and type(entry[1].get("Custom")) is int:
                report["custom_error_code"] = entry[1]["Custom"]
        return report
    accounts = value.get("accounts")
    require(isinstance(accounts, list) and len(accounts) == 2, "SIMULATED_ACCOUNTS_MISSING")
    report["post_fee_account"] = token_state(accounts[0], WSOL_MINT, referral)
    report["post_destination_account"] = token_state(accounts[1], USDC_MINT, wallet)
    groups = value.get("innerInstructions")
    require(isinstance(groups, list) and len(groups) <= 64, "INNER_INSTRUCTIONS_UNAVAILABLE")
    transfers = []; unknown = 0; seen_groups = set()
    known = {a["address"] for a in resolved["accounts"]}
    for group in groups:
        require(isinstance(group, dict) and type(group.get("index")) is int and 0 <= group["index"] < len(resolved["instructions"])
            and isinstance(group.get("instructions"), list) and len(group["instructions"]) <= 512, "INVALID_INNER_INSTRUCTIONS")
        require(group["index"] not in seen_groups, "DUPLICATE_INNER_GROUP")
        seen_groups.add(group["index"])
        if group["index"] != profile["route_index"]: continue
        for ix in group["instructions"]:
            require(isinstance(ix, dict), "INVALID_INNER_INSTRUCTION")
            # RPC jsonParsed is recorded as provider interpretation, not independent byte decoding.
            parsed = ix.get("parsed")
            if ix.get("programId") != TOKEN_PROGRAM or not isinstance(parsed, dict) or parsed.get("type") not in ("transfer", "transferChecked"):
                unknown += 1; continue
            info = parsed.get("info"); require(isinstance(info, dict), "INVALID_PARSED_TRANSFER")
            src, dest, auth = info.get("source"), info.get("destination"), info.get("authority")
            require(src in known and dest in known and auth in known, "TRANSFER_ACCOUNT_OUTSIDE_MESSAGE")
            quantity = info.get("amount") if parsed["type"] == "transfer" else info.get("tokenAmount", {}).get("amount")
            require(isinstance(quantity, str) and quantity.isascii() and quantity.isdigit() and len(quantity) <= 20 and int(quantity) < 2**64, "INVALID_TRANSFER_AMOUNT")
            transfers.append({"source": src, "destination": dest, "authority": auth,
                "amount_raw": str(int(quantity)), "type": parsed["type"], "evidence": "RPC_PARSED_CPI"})
    fee_in = sum(int(t["amount_raw"]) for t in transfers if t["destination"] == profile["fee_ata"])
    fee_out = sum(int(t["amount_raw"]) for t in transfers if t["source"] == profile["fee_ata"])
    dest_net = sum(int(t["amount_raw"]) for t in transfers if t["destination"] == profile["destination"]) - sum(int(t["amount_raw"]) for t in transfers if t["source"] == profile["destination"])
    report.update(parsed_token_transfers=transfers, other_or_unparsed_inner_count=unknown,
        observed_fee_in_raw=str(fee_in), observed_fee_out_raw=str(fee_out), observed_destination_net_raw=str(dest_net),
        destination_net_meets_operator_minimum=dest_net >= amount(minimum),
        fee_credit_observed_in_simulation=fee_in > 0 and fee_out == 0,
        blockers=["SIMULATION_IS_NOT_ONCHAIN_RECEIPT", "REMAINING_CPI_SEMANTICS_REQUIRE_REVIEW", "FEE_SPLIT_AND_ROUNDING_REQUIRE_RECONCILIATION"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("evidence", "output", "wallet", "input-raw", "minimum-output-raw", "fee-bps"):
        parser.add_argument("--"+name, required=True)
    args = parser.parse_args(argv)
    try:
        require(os.getenv("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower() == "false", "KEEP_PRODUCTION_FEES_DISABLED")
        require(Path(args.evidence).is_file(), "EVIDENCE_FILE_NOT_FOUND")
        require(not Path(args.output).exists(), "OUTPUT_ALREADY_EXISTS")
        require(1000000 <= amount(args.input_raw) <= 1000000000, "SIMULATION_INPUT_OUT_OF_BOUNDS")
        evidence = load_evidence(args.evidence)
        endpoint = os.getenv("SOLANA_RPC_URL", "")
        # This reparses the original unsigned bytes; never trusts an uploaded decoder report.
        resolved = inspect_resolved(evidence["order"]["transaction"], endpoint)
        referral = os.getenv("DEXSATO_JUPITER_REFERRAL_ACCOUNT", "")
        observation = verify_referral_accounts(referral, os.getenv("DEXSATO_JUPITER_REFERRAL_PARTNER", ""), rpc_url=endpoint)
        fee_ata = dict(observation.token_accounts)[WSOL_MINT]
        profile = validate_profile(evidence, resolved, args.wallet, referral, fee_ata,
            args.input_raw, args.minimum_output_raw, int(args.fee_bps))
        slot = max(observation.slot, resolved["lookup_context"]["slot"] or 0)
        result = simulate_rpc(endpoint, evidence["order"]["transaction"], slot, [fee_ata, profile["destination"]])
        report = summarize_simulation(result, resolved, profile, args.wallet, referral, args.minimum_output_raw, slot)
        report["referral_observation"] = observation.public_fields()
        if report.get('simulation_succeeded') and report.get('post_fee_account'):
            report['claim_projection'] = claim_projection(report['post_fee_account']['amount_raw'], observation.partner_share_bps)
        with Path(args.output).open("x", encoding="utf-8") as output: json.dump(report, output, indent=2)
        print(json.dumps({"status": report["status"], "execution_ready": False, "fee_receipt_verified": False}))
        return 2
    except SimulationRejected as error:
        print(json.dumps({"status": "SIMULATION_NOT_RUN_OR_INCOMPLETE", "reason": str(error), "execution_ready": False}))
    except Exception:
        print(json.dumps({"status": "SIMULATION_NOT_RUN_OR_INCOMPLETE", "reason": "INPUT_DEPENDENCY_OR_UPSTREAM_VALIDATION_FAILED", "execution_ready": False}))
    return 1


if __name__ == "__main__": raise SystemExit(main())
