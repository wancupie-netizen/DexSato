"""Operator-only V2/ALT evidence decoder. Never authorizes or submits trades.

V2 source is a pinned SECONDARY schema, not deployed-program verification.
ALT RPC data is provider evidence at the returned slot, not historical proof.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from application.jupiter_instruction_decoder import DecodeRejected, Reader, schema, decode_route
from application.jupiter_swap_service import _transaction_parts, _base58_text, JUPITER_V6_PROGRAM
from application.jupiter_referral_verification import _rpc, MAINNET_GENESIS, ReferralVerificationError

ALT_PROGRAM = "AddressLookupTab1e1111111111111111111111111"
V2_SOURCE = "https://github.com/sevenlabs-hq/carbon/blob/af70b199b39e60a1a33306e5411f8040374f8d9a/decoders/jupiter-swap-decoder/src/instructions/shared_accounts_route_v2.rs"
V2_ROLES = ["programAuthority", "userTransferAuthority", "sourceTokenAccount",
    "programSourceTokenAccount", "programDestinationTokenAccount", "destinationTokenAccount",
    "sourceMint", "destinationMint", "sourceTokenProgram", "destinationTokenProgram",
    "eventAuthority", "program"]


def decode_v2(data):
    if not isinstance(data, bytes) or not 8 <= len(data) <= 4096 or data[:8].hex() != "d19853937cfed8e9":
        raise DecodeRejected("INVALID_V2_DISCRIMINATOR_OR_SIZE")
    r = Reader(data[8:])
    args = {name: r.integer(size) for name, size in [
        ("id", 1), ("inAmount", 8), ("quotedOutAmount", 8),
        ("slippageBps", 2), ("platformFeeBps", 2), ("positiveSlippageBps", 2)]}
    count = r.integer(4)
    if not 1 <= count <= 64:
        raise DecodeRejected("ROUTE_PLAN_LIMIT")
    types = {t["name"]: t["type"] for t in schema()["types"]}
    # Reviewed Carbon ordinals 0..38 match the pinned legacy Swap definitions.
    # Newer ordinals have different payloads: never guess their lengths.
    types["Swap"] = {**types["Swap"], "variants": types["Swap"]["variants"][:39]}
    steps = []
    for _ in range(count):
        step = {"swap": r.value({"defined": "Swap"}, types), "bps": r.integer(2),
                "inputIndex": r.integer(1), "outputIndex": r.integer(1)}
        if not 1 <= step["bps"] <= 10000:
            raise DecodeRejected("INVALID_ROUTE_BPS")
        steps.append(step)
    args["routePlan"] = steps
    if r.offset != len(r.data):
        raise DecodeRejected("TRAILING_INSTRUCTION_DATA")
    if not args["inAmount"] or not args["quotedOutAmount"] or any(args[k] > 10000 for k in
            ("slippageBps", "platformFeeBps", "positiveSlippageBps")):
        raise DecodeRejected("INVALID_V2_AMOUNTS_OR_BPS")
    return {"name": "sharedAccountsRouteV2", "args": args,
            "account_roles": V2_ROLES, "idl_source": V2_SOURCE,
            "schema_authority": "PINNED_SECONDARY_SCHEMA",
            "fee_account_role_verified": False}


class MessageReader:
    def __init__(self, data):
        self.data, self.offset = data, 0

    def take(self, size):
        if size < 0 or self.offset + size > len(self.data):
            raise DecodeRejected("TRUNCATED_MESSAGE")
        result = self.data[self.offset:self.offset + size]
        self.offset += size
        return result

    def short(self):
        result = 0
        for index in range(3):
            value = self.take(1)[0]
            if index == 2 and value > 3:
                raise DecodeRejected("INVALID_SHORTVEC")
            result |= (value & 127) << (7 * index)
            if not value & 128:
                if index and value == 0:
                    raise DecodeRejected("NONCANONICAL_SHORTVEC")
                return result
        raise DecodeRejected("INVALID_SHORTVEC")


def message_layout(encoded):
    _, signatures, message, signers, keys, instructions = _transaction_parts(encoded)
    if any(s != bytes(64) for s in signatures):
        raise DecodeRejected("SIGNED_TRANSACTION_NOT_ACCEPTED")
    r = MessageReader(message)
    versioned = bool(message[0] & 128)
    if versioned and r.take(1) != b"\x80":
        raise DecodeRejected("UNSUPPORTED_MESSAGE_VERSION")
    required, readonly_signed, readonly_unsigned = r.take(3)
    size = r.short()
    if not 1 <= required <= size <= 128 or readonly_signed >= required or readonly_unsigned > size-required:
        raise DecodeRejected("INVALID_MESSAGE_HEADER")
    r.take(size * 32 + 32)
    for _ in range(r.short()):
        r.take(1)
        r.take(r.short())
        r.take(r.short())
    lookups = []
    count = r.short() if versioned else 0
    if count > 8:
        # Bounded single RPC snapshot: 8 maximum-size ALTs fit response limit.
        raise DecodeRejected("LOOKUP_SNAPSHOT_LIMIT")
    for _ in range(count):
        key = _base58_text(r.take(32))
        writable, readonly = list(r.take(r.short())), list(r.take(r.short()))
        if not writable and not readonly or len(set(writable+readonly)) != len(writable+readonly):
            raise DecodeRejected("EMPTY_OR_DUPLICATE_LOOKUP_INDEX")
        lookups.append({"address": key, "writable": writable, "readonly": readonly})
    if r.offset != len(message) or len({t["address"] for t in lookups}) != count:
        raise DecodeRejected("INVALID_LOOKUP_TABLE_LIST")
    total = size + sum(len(t["writable"])+len(t["readonly"]) for t in lookups)
    if total > 256:
        raise DecodeRejected("ACCOUNT_LIMIT")
    metas = [{"address": _base58_text(key), "is_signer": i < required,
              "is_writable": i < required-readonly_signed if i < required else i < size-readonly_unsigned,
              "source": "static"} for i, key in enumerate(keys)]
    return message, instructions, metas, lookups


def table_addresses(account, slot):
    if not isinstance(account, dict) or account.get("owner") != ALT_PROGRAM or account.get("executable") is not False:
        raise DecodeRejected("LOOKUP_OWNER_OR_TYPE_MISMATCH")
    data = account.get("data")
    if not isinstance(data, list) or len(data) != 2 or data[1] != "base64" or not isinstance(data[0], str) or len(data[0]) > 11000:
        raise DecodeRejected("INVALID_LOOKUP_ENCODING")
    try:
        raw = base64.b64decode(data[0], validate=True)
    except (ValueError, TypeError):
        raise DecodeRejected("INVALID_LOOKUP_ENCODING") from None
    if base64.b64encode(raw).decode() != data[0] or not 56 <= len(raw) <= 8248 or (len(raw)-56) % 32:
        raise DecodeRejected("INVALID_LOOKUP_SIZE")
    if int.from_bytes(raw[:4], "little") != 1 or raw[21] not in (0, 1):
        raise DecodeRejected("INVALID_LOOKUP_STATE")
    if int.from_bytes(raw[4:12], "little") != (1 << 64)-1:
        raise DecodeRejected("LOOKUP_DEACTIVATING_OR_DEACTIVATED")
    if type(slot) is not int or slot <= int.from_bytes(raw[12:20], "little"):
        raise DecodeRejected("LOOKUP_WARMUP_OR_INVALID_SLOT")
    addresses = [_base58_text(raw[i:i+32]) for i in range(56, len(raw), 32)]
    if raw[20] > len(addresses):
        raise DecodeRejected("INVALID_LOOKUP_EXTENSION_INDEX")
    return addresses, hashlib.sha256(raw).hexdigest()


def resolve_snapshot(lookups, result):
    slot = result.get("context", {}).get("slot") if isinstance(result, dict) and isinstance(result.get("context"), dict) else None
    accounts = result.get("value") if isinstance(result, dict) else None
    if type(slot) is not int or slot <= 0 or not isinstance(accounts, list) or len(accounts) != len(lookups):
        raise DecodeRejected("INVALID_LOOKUP_RPC_SNAPSHOT")
    writable, readonly, tables = [], [], []
    for table, account in zip(lookups, accounts):
        addresses, digest = table_addresses(account, slot)
        for name, target in (("writable", writable), ("readonly", readonly)):
            for index in table[name]:
                if index >= len(addresses):
                    raise DecodeRejected("LOOKUP_INDEX_OUT_OF_RANGE")
                target.append({"address": addresses[index], "is_signer": False,
                    "is_writable": name == "writable", "source": "lookup",
                    "table": table["address"], "table_index": index})
        tables.append({**table, "data_sha256": digest, "address_count": len(addresses)})
    # Solana MessageAccountKeys: static + ALL writable + ALL readonly.
    return writable + readonly, tables, slot


def inspect_resolved(encoded, rpc_url, *, request_post=None):
    message, instructions, metas, lookups = message_layout(encoded)
    try:
        url = urlsplit(rpc_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError()
    except (ValueError, TypeError):
        raise DecodeRejected("HTTPS_RPC_CONFIGURATION_REQUIRED") from None
    if _rpc(rpc_url, "getGenesisHash", [], request_post) != MAINNET_GENESIS:
        raise DecodeRejected("RPC_IS_NOT_SOLANA_MAINNET")
    tables, slot = [], None
    if lookups:
        snapshot = _rpc(rpc_url, "getMultipleAccounts", [[t["address"] for t in lookups],
            {"encoding": "base64", "commitment": "finalized"}], request_post)
        loaded, tables, slot = resolve_snapshot(lookups, snapshot)
        metas += loaded
    if len({m["address"] for m in metas}) != len(metas):
        raise DecodeRejected("DUPLICATE_MESSAGE_ACCOUNT")
    reports = []
    for i, ix in enumerate(instructions):
        accounts = [{"position": p, "index": n, **metas[n]} for p, n in enumerate(ix.account_indices)]
        report = {"index": i, "program": metas[ix.program_index]["address"],
                  "data_hex": ix.data.hex(), "instruction_accounts": accounts,
                  "status": "PROGRAM_NOT_DECODED"}
        if report["program"] == JUPITER_V6_PROGRAM:
            try:
                decoded = decode_route(ix.data)
                roles = decoded["account_roles"]
                if len(accounts) < len(roles):
                    raise DecodeRejected("MISSING_ROUTE_ACCOUNTS")
                report.update(decoded, status="LAYOUT_DECODED_ACCOUNTS_RESOLVED",
                    accounts=dict(zip(roles, accounts)), remaining_accounts=accounts[len(roles):])
            except DecodeRejected as error:
                report.update(status="UNSUPPORTED_OR_MALFORMED", reason=str(error))
        reports.append(report)
    return {"status": "RESOLVED_REVIEW_REQUIRED", "execution_ready": False,
        "transaction_fee_verified": False, "fee_receipt_verified": False,
        "message_sha256": hashlib.sha256(message).hexdigest(),
        "lookup_context": {"slot": slot, "commitment": "finalized", "network": "mainnet-beta",
            "checked_at": datetime.now(timezone.utc).isoformat(), "tables": tables,
            "note": "Current RPC snapshot, not capture-time state or cryptographic proof."},
        "account_count": len(metas), "loaded_writable_count": sum(m["source"] == "lookup" and m["is_writable"] for m in metas),
        "loaded_readonly_count": sum(m["source"] == "lookup" and not m["is_writable"] for m in metas),
        "accounts": metas, "instructions": reports,
        "note": "Layout and address resolution only. Remaining account semantics, CPI effects and fee receipt are NOT verified."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if os.getenv("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower() != "false":
            raise DecodeRejected("KEEP_PRODUCTION_FEES_DISABLED")
        with Path(args.evidence).open("rb") as source:
            raw = source.read(131073)
        if len(raw) > 131072:
            raise DecodeRejected("EVIDENCE_TOO_LARGE")
        evidence = json.loads(raw.decode("utf-8-sig"))
        report = inspect_resolved(evidence["order"]["transaction"], os.getenv("SOLANA_RPC_URL", ""))
        # Exclusive create: never overwrite capture, report, code or configuration.
        with Path(args.output).open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
        print(json.dumps({"status": report["status"], "execution_ready": False, "fee_receipt_verified": False}))
        return 0
    except (DecodeRejected, ReferralVerificationError) as error:
        print(json.dumps({"status": "NOT_RESOLVED", "reason": str(error), "execution_ready": False}))
    except Exception:
        print(json.dumps({"status": "NOT_RESOLVED", "reason": "INVALID_INPUT_OR_OUTPUT_UNAVAILABLE", "execution_ready": False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
