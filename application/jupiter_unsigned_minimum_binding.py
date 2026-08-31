"""Offline canonical unsigned-message/header binding, not execution approval."""
import base64
import binascii
import hashlib

from solders.message import MessageV0, to_bytes_versioned
from solders.transaction import VersionedTransaction

from application.jupiter_minimum_contract import (
    JUPITER, MinimumContractRejected, audit_minimum_contract, require,
)


def audit_unsigned_minimum(encoded, order, expected_message_sha256, resolved=None):
    """Hash bytes, select a static Jupiter V2 header, compare an order.

    Only canonical version-0 transactions with one unsigned writable payer and
    static program IDs are supported. ALT contents, route tail semantics,
    expected wallet/mints, fees and enforced minimum remain unverified.
    A hash provided alongside attacker-controlled bytes is not authentication.
    """
    require(type(encoded) is str and 0 < len(encoded) <= 1644, "INVALID_TRANSACTION_BASE64")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise MinimumContractRejected("INVALID_TRANSACTION_BASE64") from None
    require(0 < len(raw) <= 1232 and base64.b64encode(raw).decode() == encoded,
            "NONCANONICAL_OR_OVERSIZED_TRANSACTION")
    try:
        tx = VersionedTransaction.from_bytes(raw)
        tx.sanitize()
    except Exception:
        raise MinimumContractRejected("MALFORMED_TRANSACTION") from None
    require(bytes(tx) == raw, "NONCANONICAL_TRANSACTION_BYTES")
    require(isinstance(tx.message, MessageV0), "UNSUPPORTED_MESSAGE_VERSION")
    require(len(tx.signatures) == 1 and tx.message.header.num_required_signatures == 1
            and tx.message.header.num_readonly_signed_accounts == 0, "UNSUPPORTED_SIGNERS")
    require(all(bytes(sig) == bytes(64) for sig in tx.signatures), "SIGNED_TRANSACTION_REJECTED")
    message = to_bytes_versioned(tx.message)
    message_hash = hashlib.sha256(message).hexdigest()
    require(message_hash == expected_message_sha256, "TRANSACTION_MESSAGE_HASH_MISMATCH")
    keys = tx.message.account_keys
    instructions = tx.message.instructions
    require(1 <= len(instructions) <= 64, "INVALID_INSTRUCTION_COUNT")
    require(all(ix.program_id_index < len(keys) for ix in instructions),
            "LOOKUP_PROGRAM_UNSUPPORTED")
    routes = [(i, ix) for i, ix in enumerate(instructions)
              if str(keys[ix.program_id_index]) == JUPITER]
    require(len(routes) == 1, "AMBIGUOUS_OR_MISSING_JUPITER_ROUTE")
    index, instruction = routes[0]
    data = bytes(instruction.data)
    require(len(data) >= 37, "TRUNCATED_V2_HEADER")
    require(len(instruction.accounts) >= 12, "MISSING_V2_ACCOUNT_ROLES")
    args = {"inAmount": int.from_bytes(data[9:17], "little"),
            "quotedOutAmount": int.from_bytes(data[17:25], "little"),
            "slippageBps": int.from_bytes(data[25:27], "little")}
    route = {"index": index, "program": JUPITER, "name": "sharedAccountsRouteV2",
             "data_hex": data.hex(), "args": args}
    byte_report = {"message_sha256": message_hash, "instructions": [route]}
    result = audit_minimum_contract(order, byte_report, expected_message_sha256)
    if resolved is not None:
        # Compare supplied report to extracted bytes; do not trust its hash alone.
        audit_minimum_contract(order, resolved, message_hash)
        reported = next(ix for ix in resolved["instructions"] if ix.get("program") == JUPITER)
        require(type(reported.get("index")) is int and reported["index"] == index,
                "REPORT_INSTRUCTION_INDEX_MISMATCH")
        require(reported.get("data_hex", "").lower() == data.hex(), "REPORT_INSTRUCTION_BYTES_MISMATCH")
    result.update(
        status="UNSIGNED_MINIMUM_BYTE_BINDING_REVIEW_REQUIRED",
        message_hash_status="RECOMPUTED_FROM_CANONICAL_UNSIGNED_MESSAGE",
        transaction_sha256=hashlib.sha256(raw).hexdigest(),
        instruction_index=index,
        instruction_sha256=hashlib.sha256(data).hexdigest(),
        minimum_header_bytes_bound=True,
        supplied_report_bytes_matched=resolved is not None,
        lookup_state_verified=False,
        route_semantics_verified=False,
        reasons=[r for r in result["reasons"] if r != "REPORT_IS_NOT_TRANSACTION_PROOF"]
                + ["WALLET_MINT_ROUTE_FEE_AND_LOOKUP_BINDING_NOT_VERIFIED"],
    )
    return result
