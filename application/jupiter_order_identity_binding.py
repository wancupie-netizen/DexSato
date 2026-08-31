"""Offline V2 identity binding against supplied raw RPC account snapshots.

No RPC requests or execution approval. Snapshot authenticity/freshness and
program/CPI effects are NOT proved. Classic SPL Token, existing accounts only.
"""
import base64
import binascii
import hashlib

from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from application.jupiter_minimum_contract import MinimumContractRejected, require
from application.jupiter_unsigned_minimum_binding import audit_unsigned_minimum

TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ALT = "AddressLookupTab1e1111111111111111111111111"
U64_MAX = (1 << 64) - 1


def address(value):
    require(type(value) is str and 32 <= len(value) <= 44, "INVALID_IDENTITY_ADDRESS")
    try:
        key = Pubkey.from_string(value)
    except ValueError:
        raise MinimumContractRejected("INVALID_IDENTITY_ADDRESS") from None
    require(str(key) == value, "NONCANONICAL_IDENTITY_ADDRESS")
    return value


def account_bytes(accounts, key, owner, minimum, maximum):
    entry = accounts.get(key)
    require(type(entry) is dict, "ACCOUNT_SNAPSHOT_MISSING")
    require(entry.get("owner") == owner and entry.get("executable") is False,
            "ACCOUNT_PROGRAM_OWNER_OR_EXECUTABLE_MISMATCH")
    data = entry.get("data")
    require(type(data) is list and len(data) == 2 and data[1] == "base64"
            and type(data[0]) is str and len(data[0]) <= ((maximum + 2) // 3) * 4,
            "INVALID_ACCOUNT_ENCODING")
    try:
        raw = base64.b64decode(data[0], validate=True)
    except (ValueError, binascii.Error):
        raise MinimumContractRejected("INVALID_ACCOUNT_ENCODING") from None
    require(minimum <= len(raw) <= maximum and base64.b64encode(raw).decode() == data[0],
            "INVALID_ACCOUNT_SIZE_OR_ENCODING")
    return raw


def resolve_keys(message, accounts, slot):
    """Derive static + ALL loaded writable + ALL loaded readonly from ALT bytes."""
    header = message.header
    static = list(message.account_keys)
    metas = [(str(key), i < header.num_required_signatures,
              i < header.num_required_signatures - header.num_readonly_signed_accounts
              if i < header.num_required_signatures else i < len(static) - header.num_readonly_unsigned_accounts)
             for i, key in enumerate(static)]
    writable, readonly, hashes, seen = [], [], {}, set()
    require(len(message.address_table_lookups) <= 8, "LOOKUP_SNAPSHOT_LIMIT")
    for lookup in message.address_table_lookups:
        key = str(lookup.account_key)
        require(key not in seen, "DUPLICATE_LOOKUP_TABLE")
        seen.add(key)
        indices = list(lookup.writable_indexes) + list(lookup.readonly_indexes)
        require(indices and len(indices) == len(set(indices)), "EMPTY_OR_DUPLICATE_LOOKUP_INDEX")
        raw = account_bytes(accounts, key, ALT, 56, 8248)
        require((len(raw) - 56) % 32 == 0 and int.from_bytes(raw[:4], "little") == 1,
                "INVALID_LOOKUP_LAYOUT")
        require(int.from_bytes(raw[4:12], "little") == U64_MAX, "LOOKUP_DEACTIVATED")
        require(slot > int.from_bytes(raw[12:20], "little"), "LOOKUP_WARMUP")
        entries = [str(Pubkey.from_bytes(raw[i:i+32])) for i in range(56, len(raw), 32)]
        require(raw[21] in (0, 1) and raw[20] <= len(entries), "INVALID_LOOKUP_METADATA")
        for indexes, target, is_writable in ((lookup.writable_indexes, writable, True),
                                             (lookup.readonly_indexes, readonly, False)):
            for index in indexes:
                require(index < len(entries), "LOOKUP_INDEX_OUT_OF_RANGE")
                target.append((entries[index], False, is_writable))
        hashes[key] = hashlib.sha256(raw).hexdigest()
    metas += writable + readonly
    require(len(metas) <= 256 and len({m[0] for m in metas}) == len(metas),
            "DUPLICATE_OR_EXCESSIVE_MESSAGE_ACCOUNTS")
    return metas, hashes


def token_account(accounts, key, mint, wallet):
    raw = account_bytes(accounts, key, TOKEN, 165, 165)
    require(str(Pubkey.from_bytes(raw[:32])) == mint, "TOKEN_ACCOUNT_MINT_MISMATCH")
    require(str(Pubkey.from_bytes(raw[32:64])) == wallet, "TOKEN_ACCOUNT_AUTHORITY_MISMATCH")
    require(raw[108] == 1, "TOKEN_ACCOUNT_NOT_INITIALIZED_OR_FROZEN")
    # Narrow existing-account scope: no delegate or alternate close authority.
    require(int.from_bytes(raw[72:76], "little") == 0
            and int.from_bytes(raw[129:133], "little") == 0, "TOKEN_ACCOUNT_AUTHORITY_OPTIONS_UNSUPPORTED")
    require(int.from_bytes(raw[109:113], "little") in (0, 1), "INVALID_NATIVE_TOKEN_OPTION")
    return hashlib.sha256(raw).hexdigest()


def audit_order_identity(encoded, order, expected, snapshot, expected_message_sha256,
                         expected_snapshot_slot):
    """Expected identity MUST come from operator intent, not untrusted report.

    expected: wallet/input_mint/output_mint/source_token_account/destination_token_account.
    snapshot: context.slot + accounts mapping address -> raw RPC account object,
    gathered in one RPC bank snapshot by caller. This function cannot authenticate
    that claim. Missing/pre-create accounts and Token-2022 fail closed in HARNESS.
    """
    require(type(expected) is dict and type(snapshot) is dict, "INVALID_IDENTITY_EVIDENCE")
    names = ("wallet", "input_mint", "output_mint", "source_token_account", "destination_token_account")
    identity = {name: address(expected.get(name)) for name in names}
    require(identity["source_token_account"] != identity["destination_token_account"],
            "SOURCE_DESTINATION_ALIAS")
    require(identity["input_mint"] != identity["output_mint"], "INPUT_OUTPUT_MINT_ALIAS")
    context = snapshot.get("context")
    require(type(context) is dict and type(expected_snapshot_slot) is int
            and 0 < expected_snapshot_slot <= U64_MAX
            and type(context.get("slot")) is int and context["slot"] == expected_snapshot_slot,
            "SNAPSHOT_SLOT_MISMATCH")
    accounts = snapshot.get("accounts")
    require(type(accounts) is dict and len(accounts) <= 16, "INVALID_ACCOUNT_SNAPSHOT")
    result = audit_unsigned_minimum(encoded, order, expected_message_sha256)
    for field, name in (("taker", "wallet"), ("inputMint", "input_mint"), ("outputMint", "output_mint")):
        require(order.get(field) == identity[name], "ORDER_IDENTITY_MISMATCH")
    tx = VersionedTransaction.from_bytes(base64.b64decode(encoded, validate=True))
    metas, lookup_hashes = resolve_keys(tx.message, accounts, expected_snapshot_slot)
    require(metas[0] == (identity["wallet"], True, True), "PAYER_WALLET_MISMATCH")
    instruction = tx.message.instructions[result["instruction_index"]]
    require(all(index < len(metas) for index in instruction.accounts), "ACCOUNT_INDEX_OUT_OF_RANGE")
    roles = [metas[index] for index in instruction.accounts]
    require(roles[1] == (identity["wallet"], True, True), "TRANSFER_AUTHORITY_MISMATCH")
    require(roles[2][0] == identity["source_token_account"] and roles[2][2]
            and not roles[2][1], "SOURCE_TOKEN_ACCOUNT_MISMATCH")
    require(roles[5][0] == identity["destination_token_account"] and roles[5][2]
            and not roles[5][1], "DESTINATION_TOKEN_ACCOUNT_MISMATCH")
    require(roles[6][0] == identity["input_mint"] and roles[7][0] == identity["output_mint"],
            "INSTRUCTION_MINT_MISMATCH")
    require(roles[8][0] == TOKEN and roles[9][0] == TOKEN, "TOKEN_PROGRAM_UNSUPPORTED")
    require(roles[11][0] == str(tx.message.account_keys[instruction.program_id_index]),
            "JUPITER_PROGRAM_ROLE_MISMATCH")
    hashes = dict(lookup_hashes)
    for side in ("input", "output"):
        mint = identity[side + "_mint"]
        raw = account_bytes(accounts, mint, TOKEN, 82, 82)
        require(raw[45] == 1 and raw[44] <= 18, "MINT_NOT_INITIALIZED_OR_DECIMALS_UNSUPPORTED")
        require(int.from_bytes(raw[:4], "little") in (0, 1)
                and int.from_bytes(raw[46:50], "little") in (0, 1), "INVALID_MINT_AUTHORITY_OPTIONS")
        hashes[mint] = hashlib.sha256(raw).hexdigest()
    for account_name, mint_name in (("source_token_account", "input_mint"),
                                     ("destination_token_account", "output_mint")):
        hashes[identity[account_name]] = token_account(accounts, identity[account_name], identity[mint_name], identity["wallet"])
    result.update(status="PREPARED_ORDER_IDENTITY_REVIEW_REQUIRED",
                  identity_snapshot_consistent=True,
                  expected_identity=identity,
                  snapshot_slot=expected_snapshot_slot,
                  account_data_sha256=hashes,
                  snapshot_authenticity_verified=False,
                  snapshot_freshness_verified=False,
                  lookup_bytes_resolved=True,
                  reasons=[r for r in result["reasons"] if r != "WALLET_MINT_ROUTE_FEE_AND_LOOKUP_BINDING_NOT_VERIFIED"]
                          + ["SUPPLIED_SNAPSHOT_NOT_AUTHENTICATED", "FULL_ROUTE_AND_CPI_EFFECTS_UNVERIFIED"])
    return result
