"""Synthetic offline state: these tests do not claim live RPC verification."""
import base64
import copy
import hashlib

import pytest
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.signature import Signature
from solders.message import MessageV0, MessageHeader, MessageAddressTableLookup, to_bytes_versioned
from solders.instruction import CompiledInstruction
from solders.transaction import VersionedTransaction

from application.jupiter_minimum_contract import JUPITER, MinimumContractRejected
from application.jupiter_order_identity_binding import audit_order_identity, TOKEN, ALT


def key(n): return Pubkey.from_bytes(bytes([n]) * 32)
def entry(raw, owner=TOKEN): return dict(owner=owner, executable=False, data=[base64.b64encode(raw).decode(), 'base64'])


def sample():
    wallet, source, dest, im, om = [key(n) for n in range(1, 6)]
    static = [wallet, source, dest, Pubkey.from_string(TOKEN), Pubkey.from_string(JUPITER),
              key(6), key(7), key(8), key(9)]
    # Two tables exercise ALL-writable-before-ALL-readonly account ordering.
    tables = [key(10), key(11)]
    lookups = [MessageAddressTableLookup(t, bytes([1]), bytes([0])) for t in tables]
    data = bytes.fromhex('d19853937cfed8e9') + b'\x0b' + (1000000).to_bytes(8,'little')
    data += (102841).to_bytes(8,'little') + (50).to_bytes(2,'little') + bytes(10)
    roles = bytes([5,0,1,6,7,2,11,12,3,3,8,4])
    ix = CompiledInstruction(4, data, roles)
    msg = MessageV0(MessageHeader(1,0,6), static, Hash.default(), [ix], lookups)
    tx = VersionedTransaction.populate(msg, [Signature.default()])
    encoded = base64.b64encode(bytes(tx)).decode()
    expected = dict(wallet=str(wallet), input_mint=str(im), output_mint=str(om),
                    source_token_account=str(source), destination_token_account=str(dest))
    order = dict(taker=str(wallet), inputMint=str(im), outputMint=str(om),
                 inAmount='1000000', outAmount='102841', slippageBps=50, otherAmountThreshold='102326')
    accounts = {}
    for i, (t, mint) in enumerate(zip(tables, [im,om])):
        raw = bytearray(56)
        raw[:4] = (1).to_bytes(4,'little'); raw[4:12] = ((1<<64)-1).to_bytes(8,'little')
        raw[12:20] = (99).to_bytes(8,'little')
        raw += bytes(mint) + bytes(key(12+i))
        accounts[str(t)] = entry(raw, ALT)
    for mint in [im, om]:
        raw = bytearray(82); raw[44] = 6; raw[45] = 1
        accounts[str(mint)] = entry(raw)
    for token, mint in [(source,im),(dest,om)]:
        raw = bytearray(165); raw[:32] = bytes(mint); raw[32:64] = bytes(wallet); raw[108] = 1
        accounts[str(token)] = entry(raw)
    return [encoded, order, expected, dict(context=dict(slot=100), accounts=accounts),
            hashlib.sha256(to_bytes_versioned(msg)).hexdigest(), 100]


def edit_raw(entry, offset, replacement):
    raw = bytearray(base64.b64decode(entry['data'][0])); raw[offset:offset+len(replacement)] = replacement
    entry['data'][0] = base64.b64encode(raw).decode()


def test_two_lookup_tables_and_existing_token_account_identity():
    args = sample(); before = copy.deepcopy(args)
    report = audit_order_identity(*args)
    assert report['identity_snapshot_consistent'] is True
    assert report['minimum_header_bytes_bound'] is True
    assert report['lookup_bytes_resolved'] is True
    assert len(report['account_data_sha256']) == 6
    assert report['enforced_minimum_raw'] is None
    for name in ['execution_ready','transaction_binding_verified','fee_receipt_verified',
                 'enforcement_verified','production_formula_changed','snapshot_authenticity_verified',
                 'snapshot_freshness_verified','lookup_state_verified']:
        assert report[name] is False
    assert args == before


@pytest.mark.parametrize('field', ['taker','inputMint','outputMint'])
def test_order_identity_mismatch(field):
    args = sample(); args[1][field] = str(key(20))
    with pytest.raises(MinimumContractRejected, match='ORDER_IDENTITY_MISMATCH'): audit_order_identity(*args)


@pytest.mark.parametrize('name,field,code', [
    ('wallet','taker','PAYER_WALLET_MISMATCH'),
    ('input_mint','inputMint','INSTRUCTION_MINT_MISMATCH'),
    ('output_mint','outputMint','INSTRUCTION_MINT_MISMATCH'),
    ('source_token_account',None,'SOURCE_TOKEN_ACCOUNT_MISMATCH'),
    ('destination_token_account',None,'DESTINATION_TOKEN_ACCOUNT_MISMATCH')])
def test_consistent_json_change_cannot_change_transaction(name, field, code):
    args = sample(); args[2][name] = str(key(20))
    if field: args[1][field] = args[2][name]
    with pytest.raises(MinimumContractRejected, match=code): audit_order_identity(*args)


@pytest.mark.parametrize('role', ['source_token_account','destination_token_account'])
@pytest.mark.parametrize('offset,value,code', [
    (0,bytes(key(20)),'TOKEN_ACCOUNT_MINT_MISMATCH'),
    (32,bytes(key(20)),'TOKEN_ACCOUNT_AUTHORITY_MISMATCH'),
    (108,b'\0','TOKEN_ACCOUNT_NOT_INITIALIZED_OR_FROZEN'),
    (108,b'\2','TOKEN_ACCOUNT_NOT_INITIALIZED_OR_FROZEN'),
    (72,b'\1','TOKEN_ACCOUNT_AUTHORITY_OPTIONS_UNSUPPORTED'),
    (129,b'\1','TOKEN_ACCOUNT_AUTHORITY_OPTIONS_UNSUPPORTED')])
def test_raw_token_account_mismatch(role, offset, value, code):
    args = sample(); edit_raw(args[3]['accounts'][args[2][role]], offset, value)
    with pytest.raises(MinimumContractRejected, match=code): audit_order_identity(*args)


@pytest.mark.parametrize('mutation,code', [
    ('owner','ACCOUNT_PROGRAM_OWNER_OR_EXECUTABLE_MISMATCH'),
    ('executable','ACCOUNT_PROGRAM_OWNER_OR_EXECUTABLE_MISMATCH'),
    ('missing','ACCOUNT_SNAPSHOT_MISSING'), ('encoding','INVALID_ACCOUNT_ENCODING'),
    ('size','INVALID_ACCOUNT_SIZE_OR_ENCODING')])
def test_invalid_account_snapshot(mutation, code):
    args=sample(); accounts=args[3]['accounts']; address=args[2]['destination_token_account']
    if mutation=='owner': accounts[address]['owner']=str(key(20))
    if mutation=='executable': accounts[address]['executable']=True
    if mutation=='missing': del accounts[address]
    if mutation=='encoding': accounts[address]['data'][1]='jsonParsed'
    if mutation=='size': accounts[address]['data'][0]=base64.b64encode(bytes(164)).decode()
    with pytest.raises(MinimumContractRejected, match=code): audit_order_identity(*args)


@pytest.mark.parametrize('offset,value,code', [
    (4,bytes(8),'LOOKUP_DEACTIVATED'), (12,(100).to_bytes(8,'little'),'LOOKUP_WARMUP'),
    (0,bytes(4),'INVALID_LOOKUP_LAYOUT'), (56,bytes(key(20)),'INSTRUCTION_MINT_MISMATCH')])
def test_lookup_raw_state(offset,value,code):
    args=sample(); edit_raw(args[3]['accounts'][str(key(10))],offset,value)
    with pytest.raises(MinimumContractRejected, match=code): audit_order_identity(*args)


@pytest.mark.parametrize('slot', [None,True,0,99,'100'])
def test_snapshot_slot(slot):
    args=sample(); args[3]['context']['slot']=slot
    with pytest.raises(MinimumContractRejected, match='SNAPSHOT_SLOT_MISMATCH'): audit_order_identity(*args)


@pytest.mark.parametrize('offset,value', [(45,b'\0'),(44,b'\x13'),(0,b'\2')])
def test_mint_state(offset,value):
    args=sample(); edit_raw(args[3]['accounts'][args[2]['output_mint']],offset,value)
    with pytest.raises(MinimumContractRejected): audit_order_identity(*args)


@pytest.mark.parametrize('position,replacement,code', [
    (1,5,'TRANSFER_AUTHORITY_MISMATCH'), (5,1,'DESTINATION_TOKEN_ACCOUNT_MISMATCH'),
    (8,5,'TOKEN_PROGRAM_UNSUPPORTED'), (11,5,'JUPITER_PROGRAM_ROLE_MISMATCH')])
def test_instruction_role_changes_with_recomputed_hash(position,replacement,code):
    args=sample(); tx=VersionedTransaction.from_bytes(base64.b64decode(args[0])); m=tx.message
    ix=m.instructions[0]; roles=bytearray(ix.accounts); roles[position]=replacement
    changed=CompiledInstruction(ix.program_id_index,ix.data,bytes(roles))
    msg=MessageV0(m.header,m.account_keys,m.recent_blockhash,[changed],m.address_table_lookups)
    args[0]=base64.b64encode(bytes(VersionedTransaction.populate(msg,[Signature.default()]))).decode()
    args[4]=hashlib.sha256(to_bytes_versioned(msg)).hexdigest()
    with pytest.raises(MinimumContractRejected, match=code): audit_order_identity(*args)
