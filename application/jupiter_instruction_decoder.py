"""Bounded offline decoder for two pinned Jupiter V6 ExactIn layouts.

This decodes bytes, not program behavior. Unknown variants fail closed; no
last-N-byte guessing. Account lookup references remain explicitly unresolved.
"""
import hashlib
import json
import re
from pathlib import Path

from application.jupiter_swap_service import (
    _transaction_parts, _base58_text, JUPITER_V6_PROGRAM, JupiterSwapRejected,
)


class DecodeRejected(ValueError):
    pass


def schema():
    text = Path(__file__).with_name("jupiter_route_idl.json").read_text(encoding="utf-8-sig")
    if hashlib.sha256(text.encode()).hexdigest() != "6864792cecfa3fd1cdddd9c3223ff4f3fa73c26888010c036aeb3e3421d8bd97":
        raise DecodeRejected("IDL_INTEGRITY_MISMATCH")
    return json.loads(text)


class Reader:
    def __init__(self, data):
        self.data = data
        self.offset = 0

    def integer(self, size):
        end = self.offset + size
        if end > len(self.data):
            raise DecodeRejected("TRUNCATED_INSTRUCTION")
        result = int.from_bytes(self.data[self.offset:end], "little")
        self.offset = end
        return result

    def value(self, kind, types, depth=0):
        if depth > 8:
            raise DecodeRejected("IDL_DEPTH_LIMIT")
        if isinstance(kind, str):
            if kind in {"u8", "u16", "u32", "u64"}:
                return self.integer(int(kind[1:]) // 8)
            if kind == "bool":
                result = self.integer(1)
                if result > 1:
                    raise DecodeRejected("INVALID_BOOLEAN")
                return bool(result)
        if isinstance(kind, dict) and "vec" in kind:
            count = self.integer(4)
            if not 1 <= count <= 64:
                raise DecodeRejected("ROUTE_PLAN_LIMIT")
            return [self.value(kind["vec"], types, depth+1) for _ in range(count)]
        if isinstance(kind, dict) and "defined" in kind:
            definition = types[kind["defined"]]
            if definition["kind"] == "struct":
                return {f["name"]: self.value(f["type"], types, depth+1) for f in definition["fields"]}
            index = self.integer(1)
            variants = definition["variants"]
            if index >= len(variants):
                raise DecodeRejected("UNSUPPORTED_SWAP_ENUM")
            variant = variants[index]
            return {"variant": variant["name"], "fields": {
                f["name"]: self.value(f["type"], types, depth+1) for f in variant.get("fields", [])}}
        raise DecodeRejected("UNSUPPORTED_IDL_TYPE")


def decode_route(data):
    if not isinstance(data, bytes) or not 8 <= len(data) <= 4096:
        raise DecodeRejected("INVALID_INSTRUCTION_SIZE")
    if data[:8].hex() in {"d19853937cfed8e9", "bb64facc31c4af14"}:
        from application.jupiter_lookup_decoder import decode_v2
        return decode_v2(data)
    idl = schema()
    for instruction in idl["instructions"]:
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", instruction["name"]).lower()
        discriminator = hashlib.sha256(("global:"+snake).encode()).digest()[:8]
        if data[:8] == discriminator:
            reader = Reader(data[8:])
            types = {t["name"]: t["type"] for t in idl["types"]}
            args = {a["name"]: reader.value(a["type"], types) for a in instruction["args"]}
            if reader.offset != len(reader.data):
                raise DecodeRejected("TRAILING_INSTRUCTION_DATA")
            if args["slippageBps"] > 10000 or args["inAmount"] == 0 or args["quotedOutAmount"] == 0:
                raise DecodeRejected("INVALID_ROUTE_AMOUNTS")
            if any(not 1 <= step["percent"] <= 100 for step in args["routePlan"]):
                raise DecodeRejected("INVALID_ROUTE_PERCENT")
            return {"name": instruction["name"], "args": args,
                    "account_roles": [a["name"] for a in instruction["accounts"]],
                    "idl_source": idl["source"]}
    raise DecodeRejected("UNSUPPORTED_JUPITER_DISCRIMINATOR")


def inspect_transaction(encoded):
    _, signatures, message, signers, keys, instructions = _transaction_parts(encoded)
    if any(s != bytes(64) for s in signatures):
        raise DecodeRejected("SIGNED_TRANSACTION_NOT_ACCEPTED")
    reports = []
    for index, instruction in enumerate(instructions):
        program = _base58_text(keys[instruction.program_index]) if instruction.program_index < len(keys) else None
        report = {"index": index, "program": program, "discriminator_hex": instruction.data[:8].hex()}
        if program != JUPITER_V6_PROGRAM:
            report["status"] = "PROGRAM_NOT_DECODED" if program else "LOOKUP_PROGRAM_UNRESOLVED"
        else:
            try:
                decoded = decode_route(instruction.data)
                if len(instruction.account_indices) < len(decoded["account_roles"]):
                    raise DecodeRejected("MISSING_ROUTE_ACCOUNTS")
                report.update(decoded)
                report["accounts"] = {
                    role: {"index": account_index, "address": _base58_text(keys[account_index]) if account_index < len(keys) else None}
                    for role, account_index in zip(decoded["account_roles"], instruction.account_indices)}
                report["status"] = "LAYOUT_DECODED" if all(a["address"] for a in report["accounts"].values()) else "LAYOUT_DECODED_LOOKUPS_UNRESOLVED"
            except DecodeRejected as error:
                report.update(status="UNSUPPORTED_OR_MALFORMED", reason=str(error))
        reports.append(report)
    return {"status": "REVIEW_REQUIRED", "execution_ready": False,
            "transaction_fee_verified": False, "fee_receipt_verified": False,
            "message_sha256": hashlib.sha256(message).hexdigest(),
            "signers": [_base58_text(k) for k in signers], "instructions": reports,
            "note": "Decoded layout only; all account roles, lookup state and fee effects still require verification."}
