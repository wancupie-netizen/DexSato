import base64
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from application import jupiter_pool_validation as d


def pub(n):
    return d.b58encode(bytes([n])*32)


def account(raw, owner):
    return {'data': [base64.b64encode(raw).decode(), 'base64'], 'owner': owner, 'executable': False}


def route_prefix():
    return ['Program '+d.TOKEN+' '+event for _ in range(6) for event in ('invoke [1]', 'success')] + ['Program '+d.JUPITER+' invoke [1]']


def fixture():
    config, observation, pool, v0, v1 = map(pub, range(2, 7))
    a = [pub(10), config, pool, pub(11), pub(12), v0, v1, observation, d.TOKEN, pub(13)]
    data = hashlib.sha256(b'global:swap').digest()[:8] + (510634).to_bytes(8, 'little') + bytes(24) + b'\1'
    ix = {'programId': d.PANCAKE, 'stackHeight': 2, 'accounts': a, 'data': d.b58encode(data)}
    raw = bytearray(1544); raw[:8] = hashlib.sha256(b'account:PoolState').digest()[:8]
    raw[9:41] = d.key(config); raw[73:105] = d.key(d.WSOL); raw[105:137] = d.key(d.USDC)
    raw[137:169] = d.key(v0); raw[169:201] = d.key(v1); raw[201:233] = d.key(observation)
    def vault(mint):
        b = bytearray(165); b[:32] = d.key(mint); b[32:64] = d.key(pool); b[108] = 1
        b[109:113] = (1 if mint == d.WSOL else 0).to_bytes(4, 'little')
        return account(b, d.TOKEN)
    result = {'context': {'slot': 100}, 'value': [account(raw, d.PANCAKE), vault(d.WSOL), vault(d.USDC)]}
    return ix, result, [pool, v0, v1]


class BindingTests(unittest.TestCase):
    def check_snapshot(self, change=None):
        ix, result, addresses = fixture()
        if change:
            change(ix, result, addresses)
        # Structural unit fixture only; PDA derivation independently exercised below.
        with patch.object(d, 'pda', side_effect=addresses):
            return d.validate_pancake_snapshot(ix, result, addresses, 99)

    def test_candidate_never_authorizes(self):
        r = self.check_snapshot()
        self.assertEqual(r['status'], 'CANDIDATE_LAYOUT_BINDING_MATCHED')
        self.assertFalse(r['execution_ready']); self.assertFalse(r['deployed_bytecode_verified'])

    def test_owner_executable_stale_count_and_address_mutations(self):
        mutations = [lambda i,r,a:r['value'][0].update(owner=d.JUPITER),
                     lambda i,r,a:r['value'][1].update(executable=True),
                     lambda i,r,a:r['context'].update(slot=98),
                     lambda i,r,a:r['context'].update(slot=True),
                     lambda i,r,a:r['value'].pop(), lambda i,r,a:a.reverse()]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(d.BindingRejected):
                self.check_snapshot(mutate)

    def test_pool_and_vault_bytes_mutations(self):
        for index, offset in [(0,0),(0,9),(0,73),(0,137),(0,201), (1,0),(1,32),(1,72),(1,108),(1,109),(1,121),(1,129)]:
            def mutate(i,r,a):
                raw=bytearray(base64.b64decode(r['value'][index]['data'][0])); raw[offset]^=1
                r['value'][index]['data'][0]=base64.b64encode(raw).decode()
            with self.subTest(index=index,offset=offset), self.assertRaises(d.BindingRejected):
                self.check_snapshot(mutate)

    def test_wrong_pda_rejected(self):
        ix,r,a=fixture()
        with patch.object(d,'pda',return_value=pub(20)), self.assertRaises(d.BindingRejected):
            d.validate_pancake_snapshot(ix,r,a,99)

    def test_cpi_program_signer_encoding_and_alias(self):
        for field,value in [('programId',d.JUPITER),('stackHeight',3),('data','1'),('data','0')]:
            ix,_,_=fixture(); ix[field]=value
            with self.subTest(field=field,value=value), self.assertRaises(d.BindingRejected):d.pancake_call(ix)
        ix,_,_=fixture();ix['accounts'][6]=ix['accounts'][5]
        with self.assertRaises(d.BindingRejected):d.pancake_call(ix)

    def test_minimum_matches_but_no_enforcement_claim(self):
        r=d.minimum_arithmetic({'quotedOutAmount':102841,'slippageBps':50},
            {'outAmount':'102841','slippageBps':50,'otherAmountThreshold':'102326'},102326)
        self.assertEqual(r['candidate_minimum_raw'],'102326');self.assertFalse(r['enforcement_verified'])

    def test_minimum_tampering_and_bool_rejected(self):
        for threshold,slip,op in [('102327',50,102326),('102325',50,102326),('102326',True,102326),('102326',50,102327),('102326',50,True)]:
            with self.subTest(threshold=threshold,slip=slip,op=op),self.assertRaises(d.BindingRejected):
                d.minimum_arithmetic({'quotedOutAmount':102841,'slippageBps':slip},
                    {'outAmount':'102841','slippageBps':slip,'otherAmountThreshold':threshold},op)

    def probe(self):
        return {'context':{'slot':100},'value':{'err':{'InstructionError':[6,{'Custom':6001}]},'logs':route_prefix()+[
            'Program log: AnchorError occurred. Error Code: SlippageToleranceExceeded.',
            'Program '+d.JUPITER+' failed: custom program error: 0x1771']}}

    def test_probe_requires_jupiter_error_and_logs(self):
        r=d.probe_result(self.probe(),6,99)
        self.assertTrue(r['jupiter_slippage_rejection_observed']);self.assertFalse(r['enforcement_verified'])
        for change in [lambda x:x['value'].update(err=None),
                       lambda x:x['value']['logs'].append('Program '+d.PANCAKE+' failed: custom program error: 0x1771'),
                       lambda x:x['value'].update(logs=[]),
                       lambda x:x['value'].update(err={'InstructionError':[5,{'Custom':6001}]})]:
            result=self.probe();change(result)
            self.assertFalse(d.probe_result(result,6,99)['jupiter_slippage_rejection_observed'])

    def test_probe_stale_rejected(self):
        with self.assertRaises(d.BindingRejected):d.probe_result(self.probe(),6,101)

    def test_real_sdk_pda_vector(self):
        try:
            import solders
        except ImportError:
            self.skipTest('solders required for independent PDA vector')
        pool='8VXj6uz61v8yAu7m9pVEYNYjJwjK7WfFbRCs3YyXY6Bb'
        config='GcJVsj5MxokA4eRMUkB4cJHuZ6o9Y8MooXBViN5F1mYW'
        self.assertEqual(d.pda([b'pool',d.key(config),d.key(d.WSOL),d.key(d.USDC)],d.PANCAKE),pool)


class ProbeDiagnosticTests(unittest.TestCase):
    def result(self, err=None, logs=None):
        return d.probe_result({'context': {'slot': 100}, 'value': {'err': err, 'logs': logs}}, 6, 99)

    def test_custom_failure_is_retained_without_matching_pass(self):
        r=self.result({'InstructionError':[6,{'Custom':6024}]}, ['Program '+d.JUPITER+' failed: custom program error: 0x1788'])
        self.assertEqual(r['diagnostics']['error']['custom_code'],6024)
        self.assertEqual(r['diagnostics']['filtered_events'][0]['program_id'],d.JUPITER)
        self.assertFalse(r['jupiter_slippage_rejection_observed'])

    def test_missing_logs_returns_inconclusive_diagnostic(self):
        r=self.result({'InstructionError':[6,{'Custom':6001}]})
        self.assertFalse(r['diagnostics']['logs_available'])
        self.assertEqual(r['status'],'MINIMUM_PROBE_INCONCLUSIVE')

    def test_provider_prose_and_secrets_never_copied(self):
        secret='https://rpc.invalid/?api-key=TEST_SECRET_123'
        r=self.result({'unexpected':secret}, ['Program log: '+secret,'Program data: '+secret,
            'Program '+d.JUPITER+' failed: '+secret,
            'Program log: AnchorError '+secret+' Error Code: SlippageToleranceExceeded. Error Number: 6001.'])
        text=json.dumps(r)
        self.assertNotIn(secret,text);self.assertNotIn('TEST_SECRET_123',text)
        self.assertEqual(r['diagnostics']['error']['kind'],'UNRECOGNIZED')
        self.assertEqual(r['diagnostics']['filtered_events'][1]['error_number'],6001)

    def test_downstream_and_parent_failures_preserved(self):
        r=self.result({'InstructionError':[6,{'Custom':6001}]},[
            'Program '+d.PANCAKE+' invoke [2]',
            'Program '+d.PANCAKE+' failed: custom program error: 0x1771',
            'Program '+d.JUPITER+' failed: custom program error: 0x1771'])
        self.assertEqual(len(r['diagnostics']['filtered_events']),3)
        self.assertFalse(r['jupiter_slippage_rejection_observed'])

    def test_safe_builtin_and_transaction_error(self):
        r=self.result({'InstructionError':[2,'ComputationalBudgetExceeded']},[])
        self.assertEqual(r['diagnostics']['error']['instruction_index'],2)
        self.assertFalse(r['diagnostics']['error']['at_expected_route'])
        self.assertEqual(self.result('BlockhashNotFound',[])['diagnostics']['error']['detail'],'BlockhashNotFound')

    def test_diagnostic_bounds(self):
        logs=['Program '+d.JUPITER+' success']*200
        r=self.result(None,logs)['diagnostics']
        self.assertEqual(len(r['filtered_events']),128);self.assertEqual(r['omitted_line_count'],72)
        for logs in [['x'*8193],['x']*4097,[123]]:
            with self.assertRaises(d.BindingRejected):self.result(None,logs)

    def test_invalid_numeric_error_details_redacted(self):
        for detail in [{'Custom':True},{'Custom':-1},{'Custom':2**32}]:
            r=self.result({'InstructionError':[6,detail]},[])
            self.assertNotIn('custom_code',r['diagnostics']['error'])

    def test_anchor_text_with_complete_trace_still_matches(self):
        r=self.result({'InstructionError':[6,{'Custom':6001}]},route_prefix()+[
            'Program log: AnchorError occurred. Error Code: SlippageToleranceExceeded. Error Number: 6001.',
            'Program '+d.JUPITER+' failed: custom program error: 0x1771'])
        self.assertTrue(r['jupiter_slippage_rejection_observed'])
        self.assertFalse(r['execution_ready']);self.assertFalse(r['enforcement_verified'])


class ProbeClassificationTests(unittest.TestCase):
    def logs(self):
        return route_prefix()+[
            'Program '+d.PANCAKE+' invoke [2]', 'Program '+d.PANCAKE+' success',
            'Program '+d.JUPITER+' invoke [2]', 'Program '+d.JUPITER+' success',
            'Program '+d.JUPITER+' failed: custom program error: 0x1771']

    def classify(self, logs, error=None):
        return d.probe_result({'context':{'slot':100},'value':{'logs':logs,
            'err':error if error is not None else {'InstructionError':[6,{'Custom':6001}]}}},6,99)

    def test_numeric_jupiter_failure_without_anchor_text(self):
        r=self.classify(self.logs())
        self.assertEqual(r['status'],'NEGATIVE_MINIMUM_PROBE_OBSERVED')
        self.assertFalse(r['execution_ready']);self.assertFalse(r['enforcement_verified'])

    def test_same_code_from_downstream_not_accepted(self):
        logs=route_prefix()+['Program '+d.PANCAKE+' invoke [2]',
            'Program '+d.PANCAKE+' failed: custom program error: 0x1771',
            'Program '+d.JUPITER+' failed: custom program error: 0x1771']
        self.assertFalse(self.classify(logs)['jupiter_slippage_rejection_observed'])

    def test_missing_and_truncated_lifecycle(self):
        logs=self.logs()
        for bad in [logs[1:],logs[:-1],logs[:13]+logs[14:],logs+['Log truncated'],logs+['Program '+d.TOKEN+' invoke [1]']]:
            with self.subTest(bad=bad):self.assertFalse(self.classify(bad)['jupiter_slippage_rejection_observed'])

    def test_error_index_code_and_boolean_mismatch(self):
        for err in [{'InstructionError':[5,{'Custom':6001}]},{'InstructionError':[6,{'Custom':6024}]},
                    {'InstructionError':[True,{'Custom':6001}]},{'InstructionError':[6,{'Custom':True}]}]:
            self.assertFalse(self.classify(self.logs(),err)['jupiter_slippage_rejection_observed'])

    def test_wrong_program_or_runtime_code(self):
        for tail in ['Program '+d.PANCAKE+' failed: custom program error: 0x1771',
                     'Program '+d.JUPITER+' failed: custom program error: 0x1772']:
            self.assertFalse(self.classify(self.logs()[:-1]+[tail])['jupiter_slippage_rejection_observed'])

    def test_spoofed_prose_not_runtime_failure(self):
        logs=route_prefix()+['Program log: Program '+d.JUPITER+' failed: custom program error: 0x1771',
            'Program log: Error Code: SlippageToleranceExceeded.', 'Program '+d.JUPITER+' success']
        self.assertFalse(self.classify(logs)['jupiter_slippage_rejection_observed'])

    def test_malformed_depth_and_wrong_success_order(self):
        for line in ['Program '+d.PANCAKE+' invoke [3]', 'Program '+d.TOKEN+' success']:
            logs=self.logs();logs[13]=line
            self.assertFalse(self.classify(logs)['jupiter_slippage_rejection_observed'])

    def test_anchor_line_alone_no_longer_sufficient(self):
        r=self.classify(['Program log: Error Code: SlippageToleranceExceeded.',
            'Program '+d.JUPITER+' failed: custom program error: 0x1771'])
        self.assertFalse(r['jupiter_slippage_rejection_observed'])


class ProbeByteTests(unittest.TestCase):
    def test_only_quoted_output_and_slippage_change(self):
        tx=json.loads((Path(__file__).parent/'fixtures/jupiter_v2_unsigned.json').read_text())['transaction']
        new,report=d.make_probe(tx,6)
        before=base64.b64decode(tx);after=base64.b64decode(new)
        self.assertEqual(len(before),len(after));self.assertEqual(before[:65],after[:65])
        self.assertFalse(report['execution_ready'])
        from application.jupiter_lookup_decoder import message_layout
        _, oldix, _, _=message_layout(tx);_, newix, _, _=message_layout(new)
        for index,(a,b) in enumerate(zip(oldix,newix)):
            if index!=6:self.assertEqual(a,b)
        # Independently locate exactly the allowed ten-byte interval in the wire data.
        # V2 route prefix must be unique in this recorded fixture.
        prefix=bytes.fromhex('d19853937cfed8e9');pos=before.index(prefix)+17
        self.assertEqual(before[:pos],after[:pos]);self.assertEqual(before[pos+10:],after[pos+10:])
        self.assertEqual(after[pos+8:pos+10],bytes(2))

    def test_signed_and_wrong_route_refused(self):
        tx=json.loads((Path(__file__).parent/'fixtures/jupiter_v2_unsigned.json').read_text())['transaction']
        raw=bytearray(base64.b64decode(tx));raw[1]=1
        with self.assertRaises(Exception):d.make_probe(base64.b64encode(raw).decode(),6)
        with self.assertRaises(d.BindingRejected):d.make_probe(tx,0)


if __name__=='__main__':unittest.main()
