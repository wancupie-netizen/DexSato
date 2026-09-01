"""Operator CLI: read-only mainnet snapshot, never signs/submits/creates accounts."""
import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import requests
from solders.transaction import VersionedTransaction

from application.jupiter_minimum_contract import MinimumContractRejected, require
from application.jupiter_unsigned_minimum_binding import audit_unsigned_minimum
from application.jupiter_order_identity_binding import audit_order_identity, address
from application.jupiter_ata_lifecycle_binding import audit_ata_lifecycle

GENESIS = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"
MAX_JSON = 131072


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except MinimumContractRejected:
        raise
    except Exception:
        raise MinimumContractRejected("INVALID_JSON") from None


def rpc(endpoint, method, params, request_post=None):
    require(method in {"getGenesisHash", "getMultipleAccounts"}, "RPC_METHOD_NOT_ALLOWED")
    response = None
    try:
        response = (request_post or requests.post)(endpoint,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            timeout=(3, 12), stream=True, allow_redirects=False)
        require(response.status_code == 200, "RPC_HTTP_ERROR")
        raw = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            raw.extend(chunk)
            require(len(raw) <= MAX_JSON, "RPC_RESPONSE_TOO_LARGE")
        payload = strict_json(raw)
        require(type(payload) is dict and payload.get("jsonrpc") == "2.0"
                and type(payload.get("id")) is int and payload["id"] == 1
                and "result" in payload and "error" not in payload, "INVALID_RPC_ENVELOPE")
        return payload["result"]
    except MinimumContractRejected:
        raise
    except Exception:
        raise MinimumContractRejected("RPC_UNAVAILABLE") from None
    finally:
        if response is not None:
            response.close()


def capture_identity(evidence, intent, endpoint, *, request_post=None):
    """intent contains five E2E3 identity fields and expected message_sha256.

    Current finalized state, not transaction capture-time state. Provider-trust
    observation only: TLS/genesis response cannot prove account authenticity.
    """
    try:
        url = urlsplit(endpoint)
        require(url.scheme == "https" and bool(url.hostname) and not url.username
                and not url.password and not url.fragment, "HTTPS_RPC_CONFIGURATION_REQUIRED")
        _ = url.port
    except (ValueError, TypeError):
        raise MinimumContractRejected("HTTPS_RPC_CONFIGURATION_REQUIRED") from None
    require(type(evidence) is dict and type(evidence.get("order")) is dict and type(intent) is dict,
            "INVALID_CAPTURE_INPUT")
    order = evidence["order"]
    expected = {k: address(intent.get(k)) for k in
                ("wallet", "input_mint", "output_mint", "source_token_account", "destination_token_account")}
    encoded = order.get("transaction")
    expected_hash = intent.get("message_sha256")
    # Reject signed/mismatched order evidence BEFORE ANY RPC request.
    audit_unsigned_minimum(encoded, order, expected_hash)
    for field, key in (("taker", "wallet"), ("inputMint", "input_mint"), ("outputMint", "output_mint")):
        require(order.get(field) == expected[key], "ORDER_IDENTITY_MISMATCH")
    tx = VersionedTransaction.from_bytes(base64.b64decode(encoded, validate=True))
    require(str(tx.message.account_keys[0]) == expected["wallet"], "PAYER_WALLET_MISMATCH")
    tables = [str(t.account_key) for t in tx.message.address_table_lookups]
    require(len(tables) <= 8 and len(set(tables)) == len(tables), "INVALID_LOOKUP_TABLE_LIST")
    requested = list(dict.fromkeys(tables + [expected[k] for k in
        ("source_token_account", "destination_token_account", "input_mint", "output_mint")]))
    require(len(requested) <= 12, "SNAPSHOT_ACCOUNT_LIMIT")
    start = datetime.now(timezone.utc).isoformat()
    require(rpc(endpoint, "getGenesisHash", [], request_post) == GENESIS, "WRONG_RPC_NETWORK")
    result = rpc(endpoint, "getMultipleAccounts", [requested,
        {"encoding": "base64", "commitment": "finalized"}], request_post)
    require(type(result) is dict and type(result.get("context")) is dict,
            "INVALID_ACCOUNT_SNAPSHOT")
    slot = result["context"].get("slot")
    values = result.get("value")
    require(type(slot) is int and 0 < slot < 2**64 and type(values) is list
            and len(values) == len(requested), "INVALID_ACCOUNT_SNAPSHOT")
    # Preserve only raw public account fields; never URLs, raw errors or headers.
    accounts = {}
    for key, value in zip(requested, values):
        require(value is None or type(value) is dict, "INVALID_ACCOUNT_SNAPSHOT")
        if value is None:
            accounts[key] = None
            continue
        data = value.get("data")
        require(type(value.get("owner")) is str and type(value.get("executable")) is bool
                and type(data) is list and len(data) == 2 and data[1] == "base64"
                and type(data[0]) is str and len(data[0]) <= 11000, "INVALID_ACCOUNT_SNAPSHOT")
        try:
            decoded = base64.b64decode(data[0], validate=True)
            require(base64.b64encode(decoded).decode() == data[0], "INVALID_ACCOUNT_SNAPSHOT")
            address(value["owner"])
        except (ValueError, TypeError):
            raise MinimumContractRejected("INVALID_ACCOUNT_SNAPSHOT") from None
        accounts[key] = {"owner": value["owner"], "executable": value["executable"], "data": data}
    snapshot = {"context": {"slot": slot}, "accounts": accounts}
    missing = [key for key in requested if accounts[key] is None]
    report = dict(status="LIVE_IDENTITY_REVIEW_REQUIRED", execution_ready=False,
                  fee_receipt_verified=False, snapshot_authenticity_verified=False,
                  transaction_recency_verified=False, production_formula_changed=False,
                  network="solana-mainnet-beta", commitment="finalized",
                  requested_at=start, checked_at=datetime.now(timezone.utc).isoformat(),
                  slot=slot, message_sha256=expected_hash, requested_accounts=requested,
                  missing_accounts=missing, identity_snapshot_consistent=False)
    if missing:
        expected_missing = {expected["source_token_account"], expected["destination_token_account"]}
        if not set(missing).issubset(expected_missing):
            report.update(status="LIVE_IDENTITY_NOT_VERIFIED", reason="ACCOUNT_NOT_FOUND_AT_SNAPSHOT",
                          note="A required non-token account is absent; no inference or creation performed.")
        else:
            try:
                lifecycle = audit_ata_lifecycle(encoded, order, expected, snapshot, expected_hash, slot)
                binding = audit_order_identity(encoded, order, expected, snapshot, expected_hash, slot,
                                               precreated_token_accounts=set(missing))
                report.update(status="LIVE_IDENTITY_REVIEW_REQUIRED",
                              identity_snapshot_consistent=True, binding=binding,
                              ata_lifecycle=lifecycle,
                              note="Missing canonical ATAs are created in the bound unsigned transaction; no account was created by this audit.")
            except MinimumContractRejected as error:
                report.update(status="LIVE_IDENTITY_NOT_VERIFIED", reason=str(error),
                              note="Missing account lifecycle could not be bound; no inference or creation performed.")
    else:
        try:
            binding = audit_order_identity(encoded, order, expected, snapshot, expected_hash, slot)
            report.update(identity_snapshot_consistent=True, binding=binding)
        except MinimumContractRejected as error:
            report.update(status="LIVE_IDENTITY_NOT_VERIFIED", reason=str(error))
    return report, snapshot


def read_input(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_JSON + 1)
    require(len(raw) <= MAX_JSON, "INPUT_TOO_LARGE")
    return strict_json(raw.decode("utf-8-sig"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--output-dir", required=True, help="New directory only; never overwrite")
    args = parser.parse_args(argv)
    try:
        evidence, intent = read_input(args.evidence), read_input(args.intent)
        # Reserve output before RPC. Failures leave a diagnostic directory, not overwritten files.
        destination = Path(args.output_dir)
        destination.mkdir(parents=False, exist_ok=False)
        report, snapshot = capture_identity(evidence, intent, os.getenv("SOLANA_RPC_URL", ""))
        for name, value in (("live_identity_report.json", report), ("live_account_snapshot.json", snapshot)):
            with (destination / name).open("x", encoding="utf-8") as stream:
                json.dump(value, stream, indent=2)
        print(json.dumps({k: report[k] for k in ("status", "execution_ready", "fee_receipt_verified")}))
        return 2  # Review required, not execution success.
    except MinimumContractRejected as error:
        reason = str(error)
    except Exception:
        reason = "INPUT_CONFIGURATION_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status": "LIVE_IDENTITY_NOT_VERIFIED", "reason": reason,
                      "execution_ready": False, "fee_receipt_verified": False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
