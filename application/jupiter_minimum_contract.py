"""Offline minimum-header consistency harness; NEVER execution authorization.

Resolved JSON and its message hash are supplied evidence, not authenticated
transaction bytes. Only the pinned V2 header is compared here; route tails,
lookup state, program behavior, fees and output ownership remain unverified.
No production imports, network, signing, submission or formula selection.
"""
import re

U64_MAX = (1 << 64) - 1
JUPITER = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
DISCRIMINATOR = "d19853937cfed8e9"


class MinimumContractRejected(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise MinimumContractRejected(code)


def raw_uint(value):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value) is not None,
            "INVALID_RAW_INTEGER")
    result = int(value)
    require(result <= U64_MAX, "RAW_INTEGER_OVERFLOW")
    return result


def bps(value):
    require(type(value) is int and 0 <= value <= 10000, "INVALID_SLIPPAGE_BPS")
    return value


def format_raw_exact(value, decimals):
    """Proposed audit formatter only, not wired into browser production UI."""
    number = raw_uint(value)
    require(type(decimals) is int and 0 <= decimals <= 18, "INVALID_DECIMALS")
    if not decimals:
        return str(number)
    digits = str(number).zfill(decimals + 1)
    return digits[:-decimals] + "." + digits[-decimals:]


def audit_minimum_contract(order, resolved, expected_message_sha256):
    """Compare one prepared order with one supplied resolved V2 report.

Raises bounded reason codes for malformed/mismatching evidence. Even a match
does NOT establish transaction binding or an enforced on-chain minimum.
Never compare a stale indicative quote with a fresh prepared order here.
"""
    require(type(order) is dict and type(resolved) is dict, "INVALID_EVIDENCE")
    require(type(expected_message_sha256) is str and
            re.fullmatch(r"[0-9a-f]{64}", expected_message_sha256) is not None,
            "INVALID_EXPECTED_MESSAGE_HASH")
    require(resolved.get("message_sha256") == expected_message_sha256,
            "EVIDENCE_MESSAGE_HASH_MISMATCH")
    instructions = resolved.get("instructions")
    require(type(instructions) is list and 1 <= len(instructions) <= 256,
            "INVALID_INSTRUCTIONS")
    require(all(type(item) is dict for item in instructions), "INVALID_INSTRUCTIONS")
    routes = [item for item in instructions if item.get("program") == JUPITER]
    require(len(routes) == 1, "AMBIGUOUS_OR_MISSING_JUPITER_ROUTE")
    route = routes[0]
    require(route.get("name") in {"sharedAccountsRouteV2", "routeV2"},
            "UNSUPPORTED_ROUTE_VARIANT")
    encoded = route.get("data_hex")
    require(type(encoded) is str and 70 <= len(encoded) <= 8192 and
            len(encoded) % 2 == 0 and re.fullmatch(r"[0-9a-fA-F]+", encoded) is not None,
            "INVALID_V2_HEADER_BYTES")
    data = bytes.fromhex(encoded)
    expected_discriminator = (DISCRIMINATOR if route["name"] == "sharedAccountsRouteV2"
                              else "bb64facc31c4af14")
    require(data[:8].hex() == expected_discriminator, "UNSUPPORTED_DISCRIMINATOR")
    offset = 9 if route["name"] == "sharedAccountsRouteV2" else 8
    parsed = {"inAmount": int.from_bytes(data[offset:offset + 8], "little"),
              "quotedOutAmount": int.from_bytes(data[offset + 8:offset + 16], "little"),
              "slippageBps": int.from_bytes(data[offset + 16:offset + 18], "little")}
    args = route.get("args")
    require(type(args) is dict, "MISSING_DECODED_ARGS")
    require(all(type(args.get(key)) is int and args[key] == value
                for key, value in parsed.items()), "DECODED_HEADER_BYTES_MISMATCH")
    input_raw = raw_uint(order.get("inAmount"))
    quoted = raw_uint(order.get("outAmount"))
    minimum = raw_uint(order.get("otherAmountThreshold"))
    slip = bps(order.get("slippageBps"))
    bps(parsed["slippageBps"])
    require(input_raw > 0 and quoted > 0, "ZERO_ROUTE_AMOUNT")
    require(input_raw == parsed["inAmount"], "ORDER_INPUT_MISMATCH")
    require(quoted == parsed["quotedOutAmount"], "ORDER_QUOTED_OUTPUT_MISMATCH")
    require(slip == parsed["slippageBps"], "ORDER_SLIPPAGE_MISMATCH")
    require(0 < minimum <= quoted, "INVALID_PROVIDER_MINIMUM_RANGE")
    numerator = quoted * (10000 - slip)
    floor = numerator // 10000
    ceil = (numerator + 9999) // 10000
    if floor == ceil == minimum:
        relation = "BOTH_CANDIDATES"
    elif minimum == floor:
        relation = "FLOOR_CANDIDATE_ONLY"
    elif minimum == ceil:
        relation = "CEIL_CANDIDATE_ONLY"
    else:
        relation = "NEITHER_CANDIDATE"
    return {
        "schema_version": "E2E1",
        "status": "MINIMUM_CONTRACT_REVIEW_REQUIRED",
        "header_consistent": True,
        "message_sha256": expected_message_sha256,
        "message_hash_status": "SUPPLIED_EVIDENCE_MATCH_ONLY",
        "provider_minimum_raw": str(minimum),
        "decoded_quoted_output_raw": str(quoted),
        "decoded_slippage_bps": slip,
        "floor_candidate_raw": str(floor),
        "ceil_candidate_raw": str(ceil),
        "provider_candidate_relation": relation,
        "candidate_gap_raw": str(ceil - floor),
        "enforced_minimum_raw": None,
        "transaction_binding_verified": False,
        "enforcement_verified": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
        "production_formula_changed": False,
        "reasons": (["PROVIDER_MATCHES_NEITHER_HYPOTHESIS"] if relation == "NEITHER_CANDIDATE" else [])
                   + ["ON_CHAIN_MINIMUM_SEMANTICS_UNVERIFIED", "REPORT_IS_NOT_TRANSACTION_PROOF"],
    }
