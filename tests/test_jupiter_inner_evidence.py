import copy
import unittest
from application.jupiter_inner_evidence import capture_inner, claim_projection


class InnerEvidenceTests(unittest.TestCase):
    def test_all_seven_synthetic_other_instructions_retained(self):
        # Synthetic examples only: NOT reconstruction of the seven missing real CPIs.
        instructions = [{'programId': 'example', 'accounts': ['a','b'], 'data': str(i), 'stackHeight': 2} for i in range(7)]
        result = capture_inner({'innerInstructions': [{'index': 6, 'instructions': instructions}]}, 8)
        self.assertEqual(result['instruction_count'], 7)
        self.assertEqual([x['raw_instruction'] for x in result['groups'][0]['instructions']], instructions)
        self.assertTrue(all(x['semantics_verified'] is False for x in result['groups'][0]['instructions']))

    def test_parsed_and_compiled_preserved_with_unknown_fields(self):
        instructions = [{'programId':'token', 'parsed':{'type':'transferChecked','info':{'mint':'m','tokenAmount':{'amount':'5','decimals':9}}},'extra':42},
            {'programIdIndex': 18, 'accounts':[1,2,3], 'data':'abc'}]
        result=capture_inner({'innerInstructions':[{'index':0,'instructions':instructions}]},1)
        entries=result['groups'][0]['instructions']
        self.assertEqual(entries[0]['raw_instruction'],instructions[0]);self.assertEqual(entries[1]['format'],'RPC_COMPILED')
        instructions[0]['extra']=99
        self.assertEqual(entries[0]['raw_instruction']['extra'],42)

    def test_missing_cpi_explicit(self):
        self.assertEqual(capture_inner({},8)['status'],'UNAVAILABLE')

    def test_invalid_indices_duplicates_and_size_rejected(self):
        for groups in ([{'index':True,'instructions':[]}],[{'index':8,'instructions':[]}],
            [{'index':0,'instructions':[]},{'index':0,'instructions':[]}],
            [{'index':0,'instructions':[{'data':'x'*65537}]}]):
            with self.assertRaises(ValueError): capture_inner({'innerInstructions':groups},8)

    def test_balance_split_and_rounding(self):
        for balance,partner,project in [('5000','4000','1000'),('1','0','1'),('5001','4000','1001'),('0','0','0')]:
            result=claim_projection(balance,8000)
            self.assertEqual((result['partner_amount_raw'],result['project_amount_raw']),(partner,project))
            self.assertFalse(result['claim_executed']);self.assertFalse(result['deployed_bytecode_verified'])

    def test_invalid_claim_inputs_rejected(self):
        for balance,share in [('01',8000),('-1',8000),('18446744073709551616',8000),('1',True),('1',10001)]:
            with self.assertRaises(ValueError):claim_projection(balance,share)
