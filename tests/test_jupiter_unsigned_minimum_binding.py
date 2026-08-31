import base64
import copy
import hashlib
import json
from pathlib import Path

import pytest
from solders.message import MessageV0, to_bytes_versioned
from solders.transaction import VersionedTransaction
from solders.signature import Signature
from solders.instruction import CompiledInstruction

from application.jupiter_minimum_contract import MinimumContractRejected
from application.jupiter_unsigned_minimum_binding import audit_unsigned_minimum


def fixture():
    folder = Path(__file__).parent / 'fixtures'
    unsigned = json.loads((folder / 'jupiter_v2_unsigned.json').read_text(encoding='utf-8-sig'))
    resolved = json.loads((folder / 'jupiter_v2_resolved_audit.json').read_text(encoding='utf-8-sig'))
    order = dict(inAmount='1000000', outAmount='102841', slippageBps=50, otherAmountThreshold='102326')
    return unsigned['transaction'], order, resolved


def mutate(encoded, change):
    tx = VersionedTransaction.from_bytes(base64.b64decode(encoded))
    msg = tx.message
    instructions = list(msg.instructions)
    change(instructions)
    msg = MessageV0(msg.header, msg.account_keys, msg.recent_blockhash, instructions, msg.address_table_lookups)
    raw = bytes(VersionedTransaction.populate(msg, tx.signatures))
    return base64.b64encode(raw).decode(), hashlib.sha256(to_bytes_versioned(msg)).hexdigest()


def test_real_bytes_and_synthetic_order_are_bound_without_approval():
    encoded, order, report = fixture()
    before = copy.deepcopy((order, report))
    result = audit_unsigned_minimum(encoded, order, report['message_sha256'], report)
    assert result['minimum_header_bytes_bound'] is True
    assert result['supplied_report_bytes_matched'] is True
    assert result['floor_candidate_raw'] == '102326'
    assert result['ceil_candidate_raw'] == '102327'
    assert result['enforced_minimum_raw'] is None
    for key in ('execution_ready', 'enforcement_verified', 'transaction_binding_verified',
                'fee_receipt_verified', 'production_formula_changed', 'lookup_state_verified'):
        assert result[key] is False
    assert before == (order, report)


def test_without_report_does_not_invent_report_match():
    encoded, order, report = fixture()
    assert audit_unsigned_minimum(encoded, order, report['message_sha256'])['supplied_report_bytes_matched'] is False


def test_signed_transaction_rejected():
    encoded, order, report = fixture()
    tx = VersionedTransaction.from_bytes(base64.b64decode(encoded))
    signed = VersionedTransaction.populate(tx.message, [Signature.from_bytes(bytes([1]) * 64)])
    with pytest.raises(MinimumContractRejected, match='SIGNED_TRANSACTION_REJECTED'):
        audit_unsigned_minimum(base64.b64encode(bytes(signed)).decode(), order, report['message_sha256'])


@pytest.mark.parametrize('encoded', ['', '???', 'AAAA\n', 'A' * 1648, None])
def test_invalid_base64(encoded):
    with pytest.raises(MinimumContractRejected): audit_unsigned_minimum(encoded, {}, 'a' * 64)


@pytest.mark.parametrize('change', ['truncate', 'append', 'hash'])
def test_serialized_message_integrity(change):
    encoded, order, report = fixture()
    raw = base64.b64decode(encoded)
    if change == 'truncate': encoded = base64.b64encode(raw[:-1]).decode()
    if change == 'append': encoded = base64.b64encode(raw + b'\0').decode()
    expected = '0' * 64 if change == 'hash' else report['message_sha256']
    with pytest.raises(MinimumContractRejected): audit_unsigned_minimum(encoded, order, expected)


def test_modified_header_cannot_reuse_original_hash():
    encoded, order, report = fixture()
    def change(instructions):
        ix = instructions[6]
        data = bytearray(ix.data)
        data[17] ^= 1
        instructions[6] = CompiledInstruction(ix.program_id_index, bytes(data), ix.accounts)
    changed, new_hash = mutate(encoded, change)
    with pytest.raises(MinimumContractRejected, match='TRANSACTION_MESSAGE_HASH_MISMATCH'):
        audit_unsigned_minimum(changed, order, report['message_sha256'])
    with pytest.raises(MinimumContractRejected, match='ORDER_QUOTED_OUTPUT_MISMATCH'):
        audit_unsigned_minimum(changed, order, new_hash)


def test_report_tail_forgery_not_hidden_by_matching_header_and_hash():
    encoded, order, report = fixture()
    route = next(x for x in report['instructions'] if x.get('args'))
    route['data_hex'] = route['data_hex'][:-2] + 'ff'
    with pytest.raises(MinimumContractRejected, match='REPORT_INSTRUCTION_BYTES_MISMATCH'):
        audit_unsigned_minimum(encoded, order, report['message_sha256'], report)


def test_report_index_forgery():
    encoded, order, report = fixture()
    next(x for x in report['instructions'] if x.get('args'))['index'] = 0
    with pytest.raises(MinimumContractRejected, match='REPORT_INSTRUCTION_INDEX_MISMATCH'):
        audit_unsigned_minimum(encoded, order, report['message_sha256'], report)


def test_duplicate_jupiter_instruction():
    encoded, order, _ = fixture()
    def duplicate(instructions):
        route = instructions[6]
        instructions[:] = [route, route]
    changed, digest = mutate(encoded, duplicate)
    with pytest.raises(MinimumContractRejected, match='AMBIGUOUS_OR_MISSING_JUPITER_ROUTE'):
        audit_unsigned_minimum(changed, order, digest)
