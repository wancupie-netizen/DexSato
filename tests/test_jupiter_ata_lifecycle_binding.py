import base64
import copy
import hashlib

import pytest
from solders.hash import Hash
from solders.instruction import CompiledInstruction
from solders.message import MessageHeader, MessageV0, to_bytes_versioned
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from application.jupiter_ata_lifecycle_binding import (
    ATA, CLOSE_ACCOUNT, CREATE_IDEMPOTENT, SYSTEM, SYNC_NATIVE,
    audit_ata_lifecycle, canonical_ata,
)
from application.jupiter_live_identity_snapshot import capture_identity
from application.jupiter_minimum_contract import MinimumContractRejected
from application.jupiter_order_identity_binding import TOKEN, audit_order_identity

WALLET = "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
JUPITER = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"


def mint(decimals=6):
    raw = bytearray(82); raw[44] = decimals; raw[45] = 1
    return {"owner": TOKEN, "executable": False,
            "data": [base64.b64encode(raw).decode(), "base64"]}


def sample():
    source, destination = canonical_ata(WALLET, WSOL), canonical_ata(WALLET, USDC)
    keys = list(map(Pubkey.from_string,
        [WALLET, source, destination, WSOL, USDC, TOKEN, ATA, SYSTEM, JUPITER,
         "D8cy77BBepLMngZx6ZukaTff5hCt1HrWyKk3Hnd9oitf"]))
    route = bytes.fromhex("bb64facc31c4af14") + (1_000_000).to_bytes(8,"little") \
        + (103_637).to_bytes(8,"little") + (50).to_bytes(2,"little") \
        + (50).to_bytes(2,"little") + bytes(2) + (1).to_bytes(4,"little") + b"\x59\x01\x10\x27\x00\x01"
    instructions = [
        CompiledInstruction(6, CREATE_IDEMPOTENT, bytes([0,1,0,3,7,5])),
        CompiledInstruction(7, b"\x02\0\0\0"+(1_000_000).to_bytes(8,"little"), bytes([0,1])),
        CompiledInstruction(5, SYNC_NATIVE, bytes([1])),
        CompiledInstruction(6, CREATE_IDEMPOTENT, bytes([0,2,0,4,7,5])),
        CompiledInstruction(8, route, bytes([0,1,2,3,4,5,5,8,9,8])),
        CompiledInstruction(5, CLOSE_ACCOUNT, bytes([1,0,0])),
    ]
    message = MessageV0(MessageHeader(1,0,7), keys, Hash.default(), instructions, [])
    encoded = base64.b64encode(bytes(VersionedTransaction.populate(
        message,[Signature.default()]))).decode()
    digest = hashlib.sha256(to_bytes_versioned(message)).hexdigest()
    order = {"transaction":encoded,"taker":WALLET,"inputMint":WSOL,"outputMint":USDC,
             "inAmount":"1000000","outAmount":"103637","otherAmountThreshold":"103118",
             "slippageBps":50}
    expected = {"wallet":WALLET,"input_mint":WSOL,"output_mint":USDC,
                "source_token_account":source,"destination_token_account":destination}
    snapshot = {"context":{"slot":100},"accounts":{source:None,destination:None,
                WSOL:mint(9),USDC:mint(6)}}
    return encoded,order,expected,snapshot,digest


def test_full_canonical_lifecycle_is_bound_but_never_approved():
    encoded,order,expected,snapshot,digest=sample()
    report=audit_ata_lifecycle(encoded,order,expected,snapshot,digest,100)
    assert report['canonical_ata_derivation_verified'] is True
    assert report['create_idempotent_indices']=={'source':0,'destination':3}
    assert report['wsol_transfer_lamports']==1_000_000
    assert report['sync_native_index']==2 and report['route_index']==4
    assert report['close_wsol_index']==5 and report['source_closed_to_wallet'] is True
    assert report['execution_ready'] is False and report['fee_receipt_verified'] is False


def test_existing_identity_binding_accepts_only_explicit_lifecycle_accounts():
    encoded,order,expected,snapshot,digest=sample()
    lifecycle=audit_ata_lifecycle(encoded,order,expected,snapshot,digest,100)
    report=audit_order_identity(encoded,order,expected,snapshot,digest,100,
        precreated_token_accounts=set(lifecycle['missing_prestate_accounts']))
    assert report['identity_snapshot_consistent'] is True
    assert set(report['precreated_token_accounts'])==set(snapshot['accounts'])- {WSOL,USDC}
    assert report['account_data_sha256'][expected['source_token_account']]=='IN_TRANSACTION_CANONICAL_ATA'


@pytest.mark.parametrize('mutation,reason',[
    ('source','SOURCE_ATA_DERIVATION_MISMATCH'),
    ('amount','WSOL_TRANSFER_AMOUNT_MISMATCH'),
    ('order','ATA_LIFECYCLE_ORDER_MISMATCH'),
    ('duplicate','ATA_CREATE_COUNT_MISMATCH'),
    ('close','WSOL_LIFECYCLE_COUNT_MISMATCH'),
    ('reference','UNEXPECTED_MISSING_ATA_REFERENCE'),
])
def test_lifecycle_mutations_fail_closed(mutation,reason):
    encoded,order,expected,snapshot,digest=sample()
    if mutation=='source': expected={**expected,'source_token_account':expected['destination_token_account']}
    else:
        tx=VersionedTransaction.from_bytes(base64.b64decode(encoded)); ix=list(tx.message.instructions)
        if mutation=='amount': ix[1]=CompiledInstruction(ix[1].program_id_index,b"\x02\0\0\0"+(999_999).to_bytes(8,'little'),ix[1].accounts)
        if mutation=='order': ix[1],ix[2]=ix[2],ix[1]
        if mutation=='duplicate': ix.insert(1,ix[0])
        if mutation=='close': ix.pop()
        if mutation=='reference': ix.insert(4,CompiledInstruction(5,b"\x63",bytes([2])))
        message=MessageV0(tx.message.header,tx.message.account_keys,tx.message.recent_blockhash,ix,[])
        encoded=base64.b64encode(bytes(VersionedTransaction.populate(message,[Signature.default()]))).decode()
        digest=hashlib.sha256(to_bytes_versioned(message)).hexdigest(); order={**order,'transaction':encoded}
    with pytest.raises(MinimumContractRejected,match=reason):
        audit_ata_lifecycle(encoded,order,expected,snapshot,digest,100)


def test_live_snapshot_promotes_missing_canonical_lifecycle_to_review_required():
    encoded,order,expected,snapshot,digest=sample(); evidence={'order':order}; intent={**expected,'message_sha256':digest}
    class Response:
        status_code=200
        def __init__(self,value): self.value=value
        def iter_content(self,chunk_size):
            import json
            yield json.dumps({'jsonrpc':'2.0','id':1,'result':self.value}).encode()
        def close(self): pass
    def post(url,*,json,**kwargs):
        if json['method']=='getGenesisHash':
            from application.jupiter_live_identity_snapshot import GENESIS
            return Response(GENESIS)
        values=[snapshot['accounts'][key] for key in json['params'][0]]
        return Response({'context':{'slot':100},'value':values})
    report,_=capture_identity(evidence,intent,'https://rpc.example.test',request_post=post)
    assert report['status']=='LIVE_IDENTITY_REVIEW_REQUIRED'
    assert report['identity_snapshot_consistent'] is True
    assert report['ata_lifecycle']['lifecycle_instruction_order_verified'] is True
    assert report['execution_ready'] is False and report['fee_receipt_verified'] is False
