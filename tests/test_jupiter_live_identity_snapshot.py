import copy
import json
from pathlib import Path
import runpy

import pytest

from application.jupiter_live_identity_snapshot import (
    GENESIS, MinimumContractRejected, capture_identity, rpc, strict_json,
)

fixture_module = runpy.run_path(str(Path(__file__).with_name('test_jupiter_order_identity_binding.py')))


class Response:
    def __init__(self, value, status=200, raw=None):
        self.status_code = status; self.value = value; self.raw = raw; self.closed = False
    def iter_content(self, chunk_size):
        data = self.raw if self.raw is not None else json.dumps(
            {"jsonrpc":"2.0","id":1,"result":self.value}).encode()
        for i in range(0,len(data),chunk_size): yield data[i:i+chunk_size]
    def close(self): self.closed = True


def setup(missing=None):
    encoded, order, expected, snapshot, digest, _ = fixture_module['sample']()
    order = {**order, 'transaction': encoded}
    evidence = {'quote': {}, 'order': order}
    intent = {**expected, 'message_sha256': digest}
    requested = []
    def post(url, *, json, **kwargs):
        assert url == 'https://rpc.example.test/path'
        assert kwargs['allow_redirects'] is False and kwargs['stream'] is True
        if json['method'] == 'getGenesisHash': return Response(GENESIS)
        assert json['method'] == 'getMultipleAccounts'
        assert json['params'][1] == {'encoding':'base64','commitment':'finalized'}
        requested.extend(json['params'][0])
        values = [None if key == missing else snapshot['accounts'][key] for key in requested]
        return Response({'context': {'slot':100}, 'value':values})
    return evidence, intent, post, requested


def test_live_read_only_snapshot_runs_existing_binding():
    evidence,intent,post,requested=setup(); before=copy.deepcopy((evidence,intent))
    report,snapshot=capture_identity(evidence,intent,'https://rpc.example.test/path',request_post=post)
    assert report['status']=='LIVE_IDENTITY_REVIEW_REQUIRED'
    assert report['identity_snapshot_consistent'] is True
    assert report['binding']['minimum_header_bytes_bound'] is True
    assert report['binding']['identity_snapshot_consistent'] is True
    assert report['snapshot_authenticity_verified'] is False
    assert report['transaction_recency_verified'] is False
    assert report['execution_ready'] is False and report['fee_receipt_verified'] is False
    assert list(snapshot['accounts']) == requested and len(requested)==6
    assert (evidence,intent)==before


def test_missing_account_is_reported_without_inference():
    evidence,intent,_,_=setup(); missing=intent['destination_token_account']
    evidence,intent,post,_=setup(missing)
    report,snapshot=capture_identity(evidence,intent,'https://rpc.example.test/path',request_post=post)
    assert report['status']=='LIVE_IDENTITY_NOT_VERIFIED'
    assert report['reason'] in {'SOURCE_ATA_DERIVATION_MISMATCH','DESTINATION_ATA_DERIVATION_MISMATCH'}
    assert report['missing_accounts']==[missing] and snapshot['accounts'][missing] is None
    assert report['identity_snapshot_consistent'] is False


def test_identity_mismatch_happens_before_rpc():
    evidence,intent,_,_=setup(); intent['wallet']=intent['output_mint']; calls=[]
    with pytest.raises(MinimumContractRejected,match='ORDER_IDENTITY_MISMATCH'):
        capture_identity(evidence,intent,'https://rpc.example.test',request_post=lambda *a,**k:calls.append(1))
    assert calls==[]


@pytest.mark.parametrize('url',['','http://rpc.test','https://u:p@rpc.test','https://rpc.test/#x','not a url'])
def test_https_endpoint_required(url):
    evidence,intent,post,_=setup()
    with pytest.raises(MinimumContractRejected,match='HTTPS_RPC_CONFIGURATION_REQUIRED'):
        capture_identity(evidence,intent,url,request_post=post)


def test_wrong_network():
    evidence,intent,_,_=setup()
    with pytest.raises(MinimumContractRejected,match='WRONG_RPC_NETWORK'):
        capture_identity(evidence,intent,'https://rpc.test',request_post=lambda *a,**k:Response('wrong'))


@pytest.mark.parametrize('raw,code',[
    (b'{"a":1,"a":2}','DUPLICATE_JSON_KEY'),(b'{"a":NaN}','INVALID_JSON'),
    (b'[] trailing','INVALID_JSON')])
def test_strict_json(raw,code):
    with pytest.raises(MinimumContractRejected,match=code): strict_json(raw)


def test_rpc_response_is_bounded_and_closed():
    response=Response(None,raw=b'x'*(131073));
    with pytest.raises(MinimumContractRejected,match='RPC_RESPONSE_TOO_LARGE'):
        rpc('https://rpc.test','getGenesisHash',[],lambda *a,**k:response)
    assert response.closed is True


@pytest.mark.parametrize('change,code',[('slot','INVALID_ACCOUNT_SNAPSHOT'),
    ('count','INVALID_ACCOUNT_SNAPSHOT'),('encoding','INVALID_ACCOUNT_SNAPSHOT'),
    ('owner','INVALID_ACCOUNT_SNAPSHOT')])
def test_malformed_account_snapshot(change,code):
    evidence,intent,base,_=setup()
    calls=0
    def post(*a,**kw):
        nonlocal calls; calls+=1
        response=base(*a,**kw)
        if calls==2:
            result=response.value
            if change=='slot': result['context']['slot']=True
            if change=='count': result['value'].pop()
            if change=='encoding': result['value'][0]['data'][1]='jsonParsed'
            if change=='owner': result['value'][0]['owner']='bad'
        return response
    with pytest.raises(MinimumContractRejected,match=code):
        capture_identity(evidence,intent,'https://rpc.example.test/path',request_post=post)
