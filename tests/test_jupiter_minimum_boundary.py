import base64
import copy
import json
from pathlib import Path
import unittest
from application import jupiter_minimum_boundary as b


def sample(hypothesis='floor'):
    calibration={'slot':100,'output':103114,'fee':'5000','pool_trace':'a'*64}
    specs=b.matrix(calibration['output'],50)
    rows=[]
    for s in specs:
        outcome=s.get(hypothesis+'_expected',s['expected'])
        rows.append({**s,'slot':100,'pool_trace':'a'*64,'outcome':outcome,
                     'output':103114 if outcome=='SUCCESS' else None,
                     'fee':'5000' if outcome=='SUCCESS' else None})
    return calibration,rows,specs


class BoundaryTests(unittest.TestCase):
    def test_matrix_exact_adjacent_and_noninteger_rounding(self):
        for n in (2,100,103114,1000000):
            for slip in (0,1,50,100):
                rows=b.matrix(n,slip)
                self.assertEqual([x['quoted'] for x in rows[:3]],[n-1,n,n+1])
                self.assertEqual(len(rows),6)
                p=rows[4]['quoted']*(10000-rows[4]['slippage'])
                self.assertEqual(p//10000,n);self.assertNotEqual(p%10000,0)
                self.assertLessEqual(rows[3]['ceil_minimum'],n)
                self.assertGreater(rows[5]['floor_minimum'],n)

    def test_invalid_amounts_and_slippage_rejected(self):
        for n,s in ((True,50),(1,50),(2**64,50),(100,True),(100,101),(100,-1)):
            with self.assertRaises(b.BindingRejected):b.matrix(n,s)

    def test_positive_never_authorizes_or_claims_receipt(self):
        report=b.classify(*sample())
        self.assertEqual(report['boundary']['status'],'SAME_BANK_BOUNDARY_OBSERVED')
        self.assertEqual(report['rounding']['status'],'FLOOR_CONSISTENT_WITH_SAMPLES')
        for field in ('execution_ready','fee_receipt_verified','general_enforcement_proven'):
            self.assertFalse(report[field])

    def test_different_slot_trace_output_fee_or_outcome_is_inconclusive(self):
        for key,value in [('slot',101),('slot',True),('pool_trace','b'*64),
                          ('output',103115),('fee','0'),('outcome','JUPITER_6001'),
                          ('quoted',1),('slippage',100)]:
            c,r,s=sample();r[0][key]=value
            self.assertEqual(b.classify(c,r,s)['boundary']['status'],'BOUNDARY_INCONCLUSIVE')
        c,r,s=sample();r[2]['outcome']='SUCCESS'
        self.assertFalse(b.classify(c,r,s)['boundary_observed'])

    def test_missing_or_reordered_probes_never_pass(self):
        c,r,s=sample()
        with self.assertRaises(b.BindingRejected):b.classify(c,r[:-1],s)
        with self.assertRaises(b.BindingRejected):b.classify(c,[],[])
        r.reverse();self.assertFalse(b.classify(c,r,s)['boundary_observed'])

    def test_calibration_may_be_older_but_all_comparison_probes_must_share_bank(self):
        c,r,s=sample()
        for row in r:row.update(slot=101,pool_trace='b'*64)
        self.assertTrue(b.classify(c,r,s)['boundary_observed'])
        r[2]['slot']=102
        self.assertFalse(b.classify(c,r,s)['boundary_observed'])

    def test_failed_equality_cannot_anchor_boundary(self):
        c,r,s=sample();r[1]['outcome']='JUPITER_6001'
        self.assertFalse(b.classify(c,r,s)['boundary_observed'])

    def test_ceil_outcome_does_not_invalidate_boundary_or_claim_fee_changed(self):
        report=b.classify(*sample('ceil'))
        self.assertTrue(report['boundary_observed'])
        self.assertEqual(report['rounding']['status'],'CEIL_CONSISTENT_WITH_SAMPLES')
        self.assertEqual(report['rounding']['hypotheses']['floor']['status'],'CONTRADICTED_BY_SAMPLES')
        self.assertEqual(report['probe_diagnostics'][4]['reasons'],[])
        self.assertNotIn('FEE_CHANGED',json.dumps(report))

    def test_rounding_drift_is_independent_and_cannot_support_hypothesis(self):
        c,r,s=sample('ceil');r[4]['slot']=101
        report=b.classify(c,r,s)
        self.assertTrue(report['boundary_observed'])
        self.assertEqual(report['rounding']['status'],'ROUNDING_INCONCLUSIVE')
        self.assertEqual(report['rounding']['hypotheses']['ceil']['status'],'INCONCLUSIVE')

    def test_unknown_failure_and_control_contradictions(self):
        c,r,s=sample('ceil');r[4]['outcome']='OTHER_FAILURE'
        report=b.classify(c,r,s)
        self.assertTrue(report['boundary_observed'])
        self.assertIn('UNCLASSIFIED_PROBE_FAILURE',report['rounding']['reasons'])
        self.assertFalse(any('FEE_CHANGED' in x for x in report['rounding']['reasons']))
        c,r,s=sample('ceil');r[3].update(outcome='JUPITER_6001',output=None,fee=None)
        report=b.classify(c,r,s)
        self.assertEqual(report['rounding']['status'],'ROUNDING_INCONCLUSIVE')
        for h in report['rounding']['hypotheses'].values():
            self.assertEqual(h['status'],'CONTRADICTED_BY_SAMPLES')

    def test_success_fee_change_and_failed_balance_claim_distinguished(self):
        c,r,s=sample();r[4]['fee']='0'
        self.assertIn('SUCCESS_FEE_CHANGED_OR_MISSING',b.classify(c,r,s)['rounding']['reasons'])
        c,r,s=sample('ceil');r[4]['fee']='0'
        self.assertIn('FAILED_PROBE_HAS_BALANCE_CLAIM',b.classify(c,r,s)['rounding']['reasons'])

    def test_hypothesis_tampering_rejected(self):
        c,r,s=sample();s[4]['ceil_expected']='SUCCESS'
        with self.assertRaises(b.BindingRejected):b.classify(c,r,s)

    def test_pool_trace_rejects_missing_and_detects_changed_transfer(self):
        inner=json.loads((Path(__file__).parent/'fixtures/typed_pool_cpi.json').read_text())
        result={'value':{'innerInstructions':[{'index':6,'instructions':inner}]}}
        before=b.pool_trace(result,6)
        inner[2]['parsed']['info']['tokenAmount']['amount']='1'
        self.assertNotEqual(b.pool_trace(result,6),before)
        with self.assertRaises(b.BindingRejected):b.pool_trace(result,5)


class BoundaryByteTests(unittest.TestCase):
    def test_only_quote_and_slippage_bytes_change(self):
        from application.jupiter_lookup_decoder import message_layout
        tx=json.loads((Path(__file__).parent/'fixtures/jupiter_v2_unsigned.json').read_text())['transaction']
        old=base64.b64decode(tx)
        for spec in b.matrix(103114,50):
            mutated=b.mutate_unsigned(tx,6,spec['quoted'],spec['slippage'])
            new=base64.b64decode(mutated);self.assertEqual(len(old),len(new))
            changes=[i for i,(x,y) in enumerate(zip(old,new)) if x!=y]
            self.assertTrue(changes);self.assertLessEqual(max(changes)-min(changes),9)
            message_layout(mutated)
            # Replacing both fields back restores every byte of the input.
            # Independently read the original header through the compiled parser.
            from application.jupiter_lookup_decoder import MessageReader
            r=MessageReader(old);r.take(64*r.short())
            if old[r.offset]&128:r.take(1)
            r.take(3);r.take(32*r.short());r.take(32)
            count=r.short()
            for i in range(count):
                r.take(1);r.take(r.short());data=r.take(r.short())
                if i==6:
                    restored=b.mutate_unsigned(mutated,6,int.from_bytes(data[17:25],'little'),int.from_bytes(data[25:27],'little'))
            self.assertEqual(restored,tx)

    def test_signed_wrong_route_and_invalid_parameters_refused(self):
        tx=json.loads((Path(__file__).parent/'fixtures/jupiter_v2_unsigned.json').read_text())['transaction']
        raw=bytearray(base64.b64decode(tx));raw[1]=1
        with self.assertRaises(Exception):b.mutate_unsigned(base64.b64encode(raw).decode(),6,100,0)
        for index,n,slip in [(0,100,0),(True,100,0),(6,True,0),(6,100,101)]:
            with self.assertRaises(b.BindingRejected):b.mutate_unsigned(tx,index,n,slip)


if __name__=='__main__':unittest.main()
