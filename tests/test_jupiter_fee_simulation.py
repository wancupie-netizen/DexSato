import base64
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from application import jupiter_fee_simulation as d

WALLET = 'J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs'
REFERRAL = '5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ'
FEE = '3vDQ2eA5mAu1Wf5podZ7rFRnamuMKC9prhaTkf8PvyUv'

def report():
    return json.loads((Path(__file__).parent/'fixtures/jupiter_v2_resolved_audit.json').read_text())

def evidence():
    quote = {'inputMint':d.WSOL_MINT,'outputMint':d.USDC_MINT,'inAmount':'1000000','outAmount':'102841',
        'otherAmountThreshold':'102326','swapMode':'ExactIn','router':'metis','feeBps':50,
        'feeMint':d.WSOL_MINT,'referralAccount':REFERRAL,'slippageBps':50,'transaction':None}
    return {'quote':quote,'order':{**quote,'taker':WALLET,'gasless':False,'signatureFeePayer':WALLET}}

def transaction():
    return json.loads((Path(__file__).parent/'fixtures/jupiter_v2_unsigned.json').read_text())['transaction']

def profile():
    r=report(); roles=r['instructions'][6]['accounts']
    # The SDK-dependent ATA derivation is patched only for this structural fixture.
    with patch.object(d,'ata',side_effect=[roles['sourceTokenAccount']['address'],roles['destinationTokenAccount']['address']]):
        return d.validate_profile(evidence(),r,WALLET,REFERRAL,FEE,'1000000','102326',50)

class SimulationTests(unittest.TestCase):
    def test_captured_profile_matches(self):
        p=profile(); self.assertEqual(p['route_index'],6)
        self.assertEqual(p['gross_fee_arithmetic_raw'],5000)

    def validate_bad(self, change):
        e=evidence(); r=report(); change(e,r)
        roles=r['instructions'][6]['accounts']
        with patch.object(d,'ata',side_effect=[roles['sourceTokenAccount']['address'],roles['destinationTokenAccount']['address']]), self.assertRaises(Exception):
            d.validate_profile(e,r,WALLET,REFERRAL,FEE,'1000000','102326',50)

    def test_fee_header_mismatch(self):
        self.validate_bad(lambda e,r:r['instructions'][6]['args'].update(platformFeeBps=0))

    def test_wallet_payer_mismatch(self):
        self.validate_bad(lambda e,r:e['order'].update(signatureFeePayer=REFERRAL))

    def test_fee_recipient_mismatch(self):
        self.validate_bad(lambda e,r:r['instructions'][6]['remaining_accounts'][0].update(address=WALLET))

    def test_sol_transfer_amount_mismatch(self):
        self.validate_bad(lambda e,r:r['instructions'][3].update(data_hex='0200000080841e0000000000'))

    def test_unknown_top_level_and_token_opcode(self):
        self.validate_bad(lambda e,r:r['instructions'][0].update(program=REFERRAL))
        self.validate_bad(lambda e,r:r['instructions'][7].update(data_hex='04'))

    def test_rpc_has_no_broadcast_and_does_not_verify_signatures(self):
        calls=[]
        class Response:
            status_code=200
            def iter_content(self,chunk_size): yield b'{"jsonrpc":"2.0","id":1,"result":{}}'
            def close(self): pass
        def post(url,**kw):calls.append(kw); return Response()
        d.simulate_rpc('https://rpc.example',transaction(),123,[FEE],post)
        request=calls[0]['json']; self.assertEqual(request['method'],'simulateTransaction')
        config=request['params'][1]
        self.assertIs(config['sigVerify'],False); self.assertIs(config['replaceRecentBlockhash'],True)
        self.assertTrue(config['innerInstructions']); self.assertEqual(config['minContextSlot'],123)
        self.assertFalse(calls[0]['allow_redirects'])

    def test_duplicate_rpc_keys_rejected(self):
        class Response:
            status_code=200
            def iter_content(self,chunk_size): yield b'{"jsonrpc":"2.0","id":1,"id":1,"result":{}}'
            def close(self): pass
        with self.assertRaises(d.SimulationRejected): d.simulate_rpc('https://rpc.example',transaction(),1,[],lambda *a,**kw:Response())

    def test_signed_bytes_never_reach_simulation_rpc(self):
        raw=bytearray(base64.b64decode(transaction()));raw[1]=1
        with patch('requests.post') as post, self.assertRaises(d.DecodeRejected):
            d.simulate_rpc('https://rpc.example',base64.b64encode(raw).decode(),1,[FEE])
        post.assert_not_called()

    def test_failed_simulation_never_reports_fee_credit(self):
        r=d.summarize_simulation({'context':{'slot':100},'value':{'err':{'InstructionError':[6,{'Custom':6001}]}}},report(),profile(),WALLET,REFERRAL,'102326',90)
        self.assertEqual(r['status'],'SIMULATION_FAILED'); self.assertEqual(r['custom_error_code'],6001)
        self.assertFalse(r['execution_ready']); self.assertNotIn('fee_credit_observed_in_simulation',r)

    def result(self):
        p=profile(); r=report()
        def transfer(src,dest,amount):return {'programId':d.TOKEN_PROGRAM,'parsed':{'type':'transfer','info':{'source':src,'destination':dest,'authority':r['instructions'][6]['accounts']['programAuthority']['address'],'amount':amount}}}
        return {'context':{'slot':100},'value':{'err':None,'accounts':[{},{}], 'innerInstructions':[{'index':6,'instructions':[
            transfer(p['source'],FEE,'4000'),transfer(r['instructions'][6]['accounts']['programDestinationTokenAccount']['address'],p['destination'],'102841')]}]}}

    def summarize(self,result):
        with patch.object(d,'token_state',return_value={'amount_raw':'999999'}):
            return d.summarize_simulation(result,report(),profile(),WALLET,REFERRAL,'102326',90)

    def test_simulated_credit_is_not_receipt_or_execution(self):
        r=self.summarize(self.result())
        self.assertTrue(r['fee_credit_observed_in_simulation']); self.assertEqual(r['observed_fee_in_raw'],'4000')
        self.assertTrue(r['destination_net_meets_operator_minimum'])
        self.assertFalse(r['transaction_fee_verified']); self.assertFalse(r['fee_receipt_verified']); self.assertFalse(r['execution_ready'])

    def test_missing_inner_or_poststate_rejected(self):
        for field in ('innerInstructions','accounts'):
            v=self.result(); v['value'][field]=None
            with self.assertRaises(d.SimulationRejected):self.summarize(v)

    def test_duplicate_groups_and_bad_slot_rejected(self):
        v=self.result();v['value']['innerInstructions']*=2
        with self.assertRaises(d.SimulationRejected):self.summarize(v)
        for slot in (True,89):
            v=self.result();v['context']['slot']=slot
            with self.assertRaises(d.SimulationRejected):self.summarize(v)

    def test_unparsed_cpi_not_guessed(self):
        v=self.result();v['value']['innerInstructions'][0]['instructions']=[{'programId':d.TOKEN_PROGRAM,'data':'unparsed'}]
        r=self.summarize(v);self.assertFalse(r['fee_credit_observed_in_simulation']);self.assertEqual(r['other_or_unparsed_inner_count'],1)

    def test_post_token_owner_and_authority_rejected(self):
        with self.assertRaises(d.SimulationRejected):d.token_state({'owner':'wrong','executable':False},d.WSOL_MINT,REFERRAL)
        raw=bytearray(165);raw[108]=1
        with self.assertRaises(d.SimulationRejected):d.token_state({'owner':d.TOKEN_PROGRAM,'executable':False,'data':[base64.b64encode(raw).decode(),'base64']},d.WSOL_MINT,REFERRAL)


def test_real_sdk_wallet_atas_match_capture():
    # Run by full pytest in the installed project (requires the existing solders dependency).
    roles=report()['instructions'][6]['accounts']
    assert d.ata(WALLET,d.WSOL_MINT)==roles['sourceTokenAccount']['address']
    assert d.ata(WALLET,d.USDC_MINT)==roles['destinationTokenAccount']['address']
