"""Offline binding for canonical ATAs created and consumed in one transaction.

This module never submits, signs, simulates, creates or closes accounts.  It
only permits a missing snapshot account to be treated as expected pre-state
when the exact unsigned message proves its bounded lifecycle.
"""
import base64

from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from application.jupiter_minimum_contract import MinimumContractRejected, raw_uint, require
from application.jupiter_order_identity_binding import TOKEN, address, resolve_keys
from application.jupiter_unsigned_minimum_binding import audit_unsigned_minimum

ATA = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
SYSTEM = "11111111111111111111111111111111"
SYNC_NATIVE = b"\x11"
CLOSE_ACCOUNT = b"\x09"
CREATE_IDEMPOTENT = b"\x01"


def canonical_ata(wallet, mint):
    wallet_key, mint_key, token_key = map(Pubkey.from_string, (wallet, mint, TOKEN))
    return str(Pubkey.find_program_address(
        [bytes(wallet_key), bytes(token_key), bytes(mint_key)], Pubkey.from_string(ATA))[0])


def _roles(ix, metas):
    require(ix.program_id_index < len(metas)
            and all(index < len(metas) for index in ix.accounts), "ACCOUNT_INDEX_OUT_OF_RANGE")
    return metas[ix.program_id_index][0], [metas[index] for index in ix.accounts]


def audit_ata_lifecycle(encoded, order, expected, snapshot, expected_hash, slot):
    names = ("wallet", "input_mint", "output_mint",
             "source_token_account", "destination_token_account")
    identity = {name: address(expected.get(name)) for name in names}
    require(canonical_ata(identity["wallet"], identity["input_mint"])
            == identity["source_token_account"], "SOURCE_ATA_DERIVATION_MISMATCH")
    require(canonical_ata(identity["wallet"], identity["output_mint"])
            == identity["destination_token_account"], "DESTINATION_ATA_DERIVATION_MISMATCH")
    result = audit_unsigned_minimum(encoded, order, expected_hash)
    tx = VersionedTransaction.from_bytes(base64.b64decode(encoded, validate=True))
    accounts = snapshot.get("accounts")
    require(type(accounts) is dict, "INVALID_ACCOUNT_SNAPSHOT")
    metas, _ = resolve_keys(tx.message, accounts, slot)
    route_index = result["instruction_index"]
    source, destination, wallet = (identity["source_token_account"],
                                   identity["destination_token_account"], identity["wallet"])
    expected_create = {
        source: [wallet, source, wallet, identity["input_mint"], SYSTEM, TOKEN],
        destination: [wallet, destination, wallet, identity["output_mint"], SYSTEM, TOKEN],
    }
    creates, transfers, syncs, closes = {source: [], destination: []}, [], [], []
    permitted = set()
    for index, ix in enumerate(tx.message.instructions):
        program, roles = _roles(ix, metas)
        addresses = [role[0] for role in roles]
        data = bytes(ix.data)
        referenced = {source, destination}.intersection(addresses)
        if program == ATA and data == CREATE_IDEMPOTENT and len(roles) == 6:
            target = addresses[1]
            if target in creates:
                require(addresses == expected_create[target], "ATA_CREATE_ROLE_MISMATCH")
                require(roles[0] == (wallet, True, True)
                        and roles[1][2] and not roles[1][1], "ATA_CREATE_META_MISMATCH")
                creates[target].append(index); permitted.add(index)
        elif program == SYSTEM and len(data) == 12 and data[:4] == b"\x02\0\0\0":
            if addresses[:2] == [wallet, source]:
                require(len(roles) == 2 and roles[0] == (wallet, True, True)
                        and roles[1][2] and not roles[1][1], "WSOL_TRANSFER_META_MISMATCH")
                transfers.append((index, int.from_bytes(data[4:], "little"))); permitted.add(index)
        elif program == TOKEN and data == SYNC_NATIVE and addresses == [source]:
            require(roles[0][2] and not roles[0][1], "SYNC_NATIVE_META_MISMATCH")
            syncs.append(index); permitted.add(index)
        elif program == TOKEN and data == CLOSE_ACCOUNT and addresses == [source, wallet, wallet]:
            require(roles[0][2] and roles[1][2] and roles[2] == (wallet, True, True),
                    "CLOSE_ACCOUNT_META_MISMATCH")
            closes.append(index); permitted.add(index)
        elif index == route_index:
            permitted.add(index)
        if referenced:
            require(index in permitted, "UNEXPECTED_MISSING_ATA_REFERENCE")
    require(all(len(creates[key]) == 1 for key in creates), "ATA_CREATE_COUNT_MISMATCH")
    require(len(transfers) == len(syncs) == len(closes) == 1, "WSOL_LIFECYCLE_COUNT_MISMATCH")
    source_create, destination_create = creates[source][0], creates[destination][0]
    transfer_index, lamports = transfers[0]
    require(lamports == raw_uint(order.get("inAmount")),
            "WSOL_TRANSFER_AMOUNT_MISMATCH")
    require(source_create < transfer_index < syncs[0] < route_index < closes[0]
            and destination_create < route_index, "ATA_LIFECYCLE_ORDER_MISMATCH")
    missing = {key for key in (source, destination) if accounts.get(key) is None}
    require(missing and all(accounts.get(key) is None for key in missing), "NO_MISSING_ATA_TO_BIND")
    result.update(status="IN_TRANSACTION_ATA_LIFECYCLE_REVIEW_REQUIRED",
                  canonical_ata_derivation_verified=True,
                  missing_prestate_accounts=sorted(missing),
                  create_idempotent_indices={"source": source_create,
                                             "destination": destination_create},
                  wsol_transfer_index=transfer_index, wsol_transfer_lamports=lamports,
                  sync_native_index=syncs[0], route_index=route_index,
                  close_wsol_index=closes[0], source_closed_to_wallet=True,
                  destination_created_before_route=True,
                  lifecycle_instruction_order_verified=True,
                  execution_ready=False, fee_receipt_verified=False,
                  transaction_submitted=False, production_formula_changed=False)
    return result
