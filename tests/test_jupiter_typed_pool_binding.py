import base64
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from solders.pubkey import Pubkey
from application import jupiter_typed_pool_binding as t


def pub(n):
    return t.b58encode(bytes([n])*32)


def acct(raw, owner=t.TOKEN):
    return {'owner': owner, 'executable': False, 'data': [base64.b64encode(raw).decode(), 'base64']}


def token(mint, authority):
    b = bytearray(165); b[:32] = t.key(mint); b[32:64] = t.key(authority)
    b[108] = 1; b[109:113] = int(mint == t.WSOL).to_bytes(4, 'little')
    return acct(b)


def fixture(program, reverse=False):
    """Synthetic states with real PDA derivation, not mainnet state evidence."""
    m0, m1 = t.WSOL, t.USDC
    authority, pool, source, dest, v0, v1, config = map(pub, range(10, 17))
    data = hashlib.sha256(b'global:swap').digest()[:8] + (50).to_bytes(8, 'little') + (10).to_bytes(8, 'little')
    raw = bytearray({t.METEORA:904,t.SABER:395,t.ORCA:653}[program])
    if program == t.METEORA:
        v0 = t.pda([t.key(pool),t.key(m0)],program); v1 = t.pda([t.key(pool),t.key(m1)],program)
        oracle = t.pda([b'oracle',t.key(pool)],program)
        a = [pool,program,v0,v1,source,dest,m0,m1,oracle,program,authority,t.TOKEN,t.TOKEN,
             t.pda([b'__event_authority'],program),program,pub(30)]
        raw[:8] = hashlib.sha256(b'account:LbPair').digest()[:8]
        for p,k in ((88,m0),(120,m1),(152,v0),(184,v1),(552,oracle)): raw[p:p+32] = t.key(k)
        poolauth = pool
    elif program == t.SABER:
        poolauth, nonce = Pubkey.find_program_address([t.key(pool)],Pubkey.from_string(program))
        poolauth = str(poolauth); raw[:3] = bytes([1,0,nonce]); admin=pub(25)
        a = [pool,poolauth,authority,source,v1 if reverse else v0,v0 if reverse else v1,dest,admin,t.TOKEN]
        for p,k in ((107,v0),(139,v1),(203,m0),(235,m1),(267,admin),(299,admin)): raw[p:p+32] = t.key(k)
        data = b'\x01'+(50).to_bytes(8,'little')+(10).to_bytes(8,'little')
    else:
        raw[:8] = hashlib.sha256(b'account:Whirlpool').digest()[:8]
        raw[8:40] = t.key(config); raw[41:43] = (64).to_bytes(2,'little'); raw[43:45] = raw[41:43]
        pool = t.pda([b'whirlpool',t.key(config),t.key(m0),t.key(m1),raw[43:45]],program)
        a = [t.TOKEN,authority,pool,dest if reverse else source,v0,source if reverse else dest,v1,
             pub(31),pub(32),pub(33),t.pda([b'oracle',t.key(pool)],program)]
        for p,k in ((101,m0),(181,m1),(133,v0),(213,v1)): raw[p:p+32] = t.key(k)
        data += bytes(16)+bytes([1,not reverse]); poolauth=pool
    ix = {'programId':program,'stackHeight':2,'accounts':a,'data':t.b58encode(data)}
    call=t.decode_call(ix); mi,mo=(m1,m0) if reverse else (m0,m1)
    vaults={v0:token(m0,poolauth),v1:token(m1,poolauth)}
    values=[acct(raw,program),vaults[call['addresses'][1]],vaults[call['addresses'][2]],
            token(mi,authority),token(mo,authority)]
    if program==t.SABER: values.append(token(mo,pub(40)))
    values.append({'owner':'BPFLoaderUpgradeab1e11111111111111111111111','executable':True})
    snapshot={'context':{'slot':100},'value':values}
    return ix,snapshot,call['addresses'],authority,set(a)|{program}


def check(f):
    return t.validate_snapshot(f[0],f[1],f[2],99,f[3],f[4])


def edit_raw(f, index, offset, value):
    raw=bytearray(base64.b64decode(f[1]['value'][index]['data'][0]))
    raw[offset:offset+len(value)]=value
    f[1]['value'][index]['data'][0]=base64.b64encode(raw).decode()


def children(b):
    edges=[(b['source'],b['input_vault'],b['authority'],50),
           (b['output_vault'],b['destination'],b['pool_authority'],20)]
    if b['admin_fee_account']:edges.append((b['output_vault'],b['admin_fee_account'],b['pool_authority'],0))
    return [{'programId':t.TOKEN,'stackHeight':3,'parsed':{'type':'transfer','info':{
        'source':s,'destination':d,'authority':a,'amount':str(n)}}} for s,d,a,n in edges]


class TypedBindingTests(unittest.TestCase):
    def test_all_families_both_directions_real_pdas_never_authorize(self):
        for p in t.PROGRAMS:
            for reverse in (False,True):
                with self.subTest(p=p,reverse=reverse):
                    b=check(fixture(p,reverse)); self.assertEqual(b['status'],'TYPED_POOL_VAULT_BINDING_MATCHED')
                    self.assertFalse(b['execution_ready']); self.assertFalse(b['deployed_bytecode_verified'])
                    self.assertEqual(b['input_mint'],t.USDC if reverse else t.WSOL)
                    self.assertEqual(t.validate_children(b,children(b))['status'],'CHILD_TRANSFER_BINDING_MATCHED')

    def test_snapshot_owner_size_state_and_mint_mutations(self):
        for p in t.PROGRAMS:
            changes=[lambda f:f[1]['value'][0].update(owner=t.TOKEN),
                     lambda f:f[1]['value'][0].update(executable=True),
                     lambda f:f[1]['value'][-1].update(executable=False),
                     lambda f:f[1]['context'].update(slot=98),
                     lambda f:f[1]['context'].update(slot=True),
                     lambda f:f[1]['value'].pop(),lambda f:f[2].reverse(),
                     lambda f:f[1]['value'].__setitem__(0,None)]
            for mutate in changes:
                with self.subTest(p=p,mutation=mutate):
                    f=fixture(p); mutate(f)
                    with self.assertRaises(t.BindingRejected):check(f)
            for index,offset,value in [(1,0,t.key(pub(50))),(2,32,t.key(pub(50))),
                (1,108,b'\2'),(1,72,b'\1'),(1,129,b'\1'),(1,121,b'\1'),
                (3,32,t.key(pub(50))),(4,0,t.key(pub(50)))]:
                with self.subTest(p=p,index=index,offset=offset):
                    f=fixture(p);edit_raw(f,index,offset,value)
                    with self.assertRaises(t.BindingRejected):check(f)

    def test_pool_specific_field_mutations(self):
        fields={t.METEORA:[0,82,88,120,152,184,552,880],
                t.SABER:[0,1,2,107,139,203,235,299],t.ORCA:[0,8,43,101,133,181,213]}
        for p,offsets in fields.items():
            for offset in offsets:
                with self.subTest(p=p,offset=offset):
                    f=fixture(p);raw=base64.b64decode(f[1]['value'][0]['data'][0])
                    edit_raw(f,0,offset,bytes([raw[offset]^255]))
                    with self.assertRaises(t.BindingRejected):check(f)

    def test_message_binding_and_route_authority(self):
        for p in t.PROGRAMS:
            f=fixture(p)
            with self.assertRaises(t.BindingRejected):t.validate_snapshot(f[0],f[1],f[2],99,pub(50),f[4])
            f[4].remove(f[0]['accounts'][0])
            with self.assertRaises(t.BindingRejected):check(f)

    def test_wrong_instruction_versions_and_aliases(self):
        for p in t.PROGRAMS:
            for mutation in ('data','stack','alias','program','count'):
                f=fixture(p);ix=f[0]
                if mutation=='data':ix['data']=t.b58encode(t.b58decode(ix['data'])+b'\0')
                if mutation=='stack':ix['stackHeight']=3
                if mutation=='alias':ix['accounts'][0]=ix['accounts'][1]
                if mutation=='program':ix['programId']=pub(50)
                if mutation=='count':ix['accounts']=ix['accounts'][:5]
                with self.subTest(p=p,mutation=mutation):
                    with self.assertRaises(t.BindingRejected):check(f)

    def test_child_transfer_mutations(self):
        for p in t.PROGRAMS:
            b=check(fixture(p))
            for mutate in [lambda x:x.pop(),lambda x:x.reverse(),lambda x:x.append(copy.deepcopy(x[0])),
                    lambda x:x[0].update(stackHeight=4),lambda x:x[0].update(programId=pub(50)),
                    lambda x:x[0]['parsed']['info'].update(destination=pub(50)),
                    lambda x:x[1]['parsed']['info'].update(authority=pub(50)),
                    lambda x:x[0]['parsed']['info'].update(amount='51'),
                    lambda x:x[1]['parsed']['info'].update(amount='0')]:
                x=children(b);mutate(x)
                with self.assertRaises(t.BindingRejected):t.validate_children(b,x)

    def test_actual_cpi_decodes_and_nested_events_are_not_swaps(self):
        inner=json.loads((Path(__file__).parent/'fixtures/typed_pool_cpi.json').read_text())
        direct=[x for x in inner if x['programId'] in t.PROGRAMS and x['stackHeight']==2]
        self.assertEqual(len(direct),3)
        self.assertEqual([t.decode_call(x)['amount_in'] for x in direct],[176911,18326,307455])
        for x in inner:
            if x['programId']==t.METEORA and x['stackHeight']==3:
                with self.assertRaises(t.BindingRejected):t.decode_call(x)
                self.assertEqual(t.b58decode(x['data'])[:8].hex(),'e445a52e51cb9a1d')

    def test_read_only_collector_coverage_and_failure_not_hidden(self):
        for p in t.PROGRAMS:
            f=fixture(p); b=check(f); inner=[f[0]]+children(b)
            fetch=lambda addresses,slot:f[1]
            rows,covered=t.audit_typed_calls(inner,f[4],f[3],99,fetch)
            self.assertEqual(covered,set(range(len(inner))));self.assertIn('binding',rows[0])
            inner[1]['parsed']['info']['destination']=pub(50)
            rows,covered=t.audit_typed_calls(inner,f[4],f[3],99,fetch)
            self.assertEqual(covered,set());self.assertEqual(rows[0]['status'],'TYPED_BINDING_NOT_MATCHED')

    def test_checked_transfer_mint_decimals_and_event_envelope(self):
        b=check(fixture(t.METEORA)); x=children(b)
        for i,mint in enumerate((b['input_mint'],b['output_mint'])):
            info=x[i]['parsed']['info'];amount=info.pop('amount')
            info.update(mint=mint,tokenAmount={'amount':amount,'decimals':9 if mint==t.WSOL else 6})
            x[i]['parsed']['type']='transferChecked'
        event={'programId':t.METEORA,'stackHeight':3,
               'accounts':[t.pda([b'__event_authority'],t.METEORA)],
               'data':t.b58encode(bytes.fromhex('e445a52e51cb9a1d')+bytes(8))}
        x.append(event)
        self.assertEqual(t.validate_children(b,x)['event_envelopes'],1)
        for mutate in [lambda y:y[0]['parsed']['info'].update(mint=t.USDT),
                       lambda y:y[0]['parsed']['info']['tokenAmount'].update(decimals=6),
                       lambda y:y[0]['parsed']['info']['tokenAmount'].update(amount=True),
                       lambda y:y[-1].update(accounts=[pub(50)]),
                       lambda y:y[-1].update(data=t.b58encode(bytes(16)))]:
            y=copy.deepcopy(x);mutate(y)
            with self.assertRaises(t.BindingRejected):t.validate_children(b,y)

    def test_unknown_child_and_invalid_parent_never_covered(self):
        f=fixture(t.METEORA);inner=[f[0]]+children(check(f))
        inner.append({'programId':pub(50),'stackHeight':3})
        rows,covered=t.audit_typed_calls(inner,f[4],f[3],99,lambda a,s:f[1])
        self.assertFalse(covered);self.assertEqual(rows[0]['reason'],'TYPED_UNKNOWN_CHILD')
        with patch.object(t,'validate_snapshot',side_effect=t.BindingRejected('REJECTED')):
            rows,covered=t.audit_typed_calls(inner,f[4],f[3],99,lambda a,s:f[1])
            self.assertFalse(covered)
        with patch.object(t,'decode_call',side_effect=t.BindingRejected('REJECTED')):
            def forbidden(*args):raise AssertionError('must reject before RPC')
            rows,covered=t.audit_typed_calls(inner,f[4],f[3],99,forbidden)
            self.assertFalse(covered)

    def test_route_link_and_intermediate_amount_mutations(self):
        rows=[]
        for ordinal,program,mi,mo,src,dst,amount,out in [
            (1,t.METEORA,t.WSOL,t.USDT,pub(10),pub(11),50,20),
            (6,t.SABER,t.USDT,t.USDC,pub(11),pub(12),20,19),
            (10,t.ORCA,t.WSOL,t.USDC,pub(10),pub(12),40,30)]:
            rows.append({'ordinal':ordinal,'binding':{'program':program,'input_mint':mi,
                'output_mint':mo,'source':src,'destination':dst,'amount_in':amount},
                'children':{'output_raw':str(out)}})
        self.assertEqual(t.validate_route_links(rows,pub(10),pub(12))['status'],'TYPED_ROUTE_LINKS_MATCHED')
        for mutate in [lambda x:x.pop(),lambda x:x.append(x[0]),
                       lambda x:x[1]['binding'].update(source=pub(50)),
                       lambda x:x[0]['binding'].update(input_mint=t.USDC),
                       lambda x:x[2]['binding'].update(destination=pub(50)),
                       lambda x:x[1]['binding'].update(amount_in=21),
                       lambda x:x[1].update(ordinal=0)]:
            x=copy.deepcopy(rows);mutate(x)
            with self.assertRaises(t.BindingRejected):t.validate_route_links(x,pub(10),pub(12))


if __name__=='__main__':unittest.main()
