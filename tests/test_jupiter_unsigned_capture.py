"""Self-contained unsigned-capture fixtures; no sibling test-module imports."""
import base64
import json
import unittest
from unittest.mock import Mock,patch
from application import jupiter_unsigned_capture as c
from application.jupiter_fee_policy import WSOL_MINT, USDC_MINT
from application.jupiter_swap_service import JUPITER_V6_PROGRAM, _base58_bytes

REFERRAL = "5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
WALLET = "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
ATA = "3vDQ2eA5mAu1Wf5podZ7rFRnamuMKC9prhaTkf8PvyUv"


def transaction(signed=False):
    # Synthetic v0 message; deliberately not a valid executable swap.
    keys = [WALLET, JUPITER_V6_PROGRAM, ATA]
    message = bytes([128, 1, 0, 1, 3])
    message += b"".join(_base58_bytes(key) for key in keys) + bytes([7])*32
    message += bytes([1, 1, 2, 0, 2, 1, 1, 0])
    return base64.b64encode(b"\1" + bytes([1 if signed else 0])*64 + message).decode()


def evidence():
    quote = dict(inputMint=WSOL_MINT, outputMint=USDC_MINT, inAmount="1000000",
                 outAmount="150000", otherAmountThreshold="140000",
                 referralAccount=REFERRAL, feeBps=50, feeMint=WSOL_MINT,
                 platformFee={"feeBps":50,"feeMint":WSOL_MINT})
    order = dict(quote, taker=WALLET, transaction=transaction())
    order["platformFee"]={"feeBps":50,"feeMint":WSOL_MINT}
    return quote, order


def env():
    return {"JUPITER_API_KEY":"test-secret", "DEXSATO_JUPITER_FEE_ENABLED":"false",
        "DEXSATO_JUPITER_REFERRAL_ACCOUNT":REFERRAL,"DEXSATO_JUPITER_REFERRAL_PARTNER":WALLET,
        "SOLANA_RPC_URL":"https://rpc.example"}


def pair():
    q,o=evidence()
    for p in (q,o): p.update(router="metis",swapMode="ExactIn",slippageBps=50)
    o.update(gasless=False,signatureFeePayer=WALLET)
    return q,o


class UnsignedCaptureTests(unittest.TestCase):
    def setUp(self):
        verifier=patch.object(c,"verify_referral_accounts",return_value=Mock(public_fields=lambda:{"status":"RPC_ACCOUNT_VERIFIED"}))
        self.verifier=verifier.start();self.addCleanup(verifier.stop)

    def run_capture(self): return c.capture(WALLET,"1000000",50,50,environment=env())

    def test_two_gets_no_taker_then_taker_and_no_execution(self):
        with patch.object(c,"get_order",side_effect=pair()) as get:
            saved,report=self.run_capture()
        self.assertNotIn("taker",get.call_args_list[0].args[0])
        self.assertEqual(get.call_args_list[1].args[0]["taker"],WALLET)
        self.assertEqual(get.call_args_list[1].args[0]["excludeRouters"],"jupiterz,dflow,okx")
        self.assertEqual(saved["order"]["transaction"],transaction())
        self.assertFalse(report["execution_ready"])
        self.assertTrue(report["capture_only"])

    def test_enabled_production_flag_rejected_before_rpc(self):
        values=env();values["DEXSATO_JUPITER_FEE_ENABLED"]="true"
        with self.assertRaisesRegex(c.CaptureRejected,"KEEP_PRODUCTION_FEES_DISABLED"):
            c.capture(WALLET,"1000000",50,50,environment=values)
        self.verifier.assert_not_called()

    def test_unverified_referral_stops_before_get(self):
        self.verifier.side_effect=ValueError("unverified")
        with patch.object(c,"get_order") as get,self.assertRaises(ValueError): self.run_capture()
        get.assert_not_called()

    def test_signed_wrong_payer_and_sponsored_order_rejected(self):
        for changes in ({"transaction":transaction(signed=True)},{"signatureFeePayer":REFERRAL},{"gasless":True}):
            q,o=pair();o.update(changes)
            with self.subTest(changes=changes),patch.object(c,"get_order",side_effect=[q,o]),self.assertRaises(c.CaptureRejected):
                self.run_capture()

    def test_bad_quote_stops_before_order_request(self):
        q,o=pair();q["transaction"]=transaction()
        with patch.object(c,"get_order",side_effect=[q,o]) as get,self.assertRaises(c.CaptureRejected): self.run_capture()
        self.assertEqual(get.call_count,1)

    def test_quote_and_order_may_omit_amount_but_any_amount_must_be_exact(self):
        q,o=pair()
        with patch.object(c,"get_order",side_effect=[q,o]): self.run_capture()
        cases=[("quote",None),("quote",{"feeBps":51,"feeMint":WSOL_MINT}),
               ("order",{"amount":"4999","feeBps":50,"feeMint":WSOL_MINT}),
               ("order",{"amount":"5000","feeBps":51,"feeMint":WSOL_MINT})]
        for target,platform in cases:
            q,o=pair();(q if target=="quote" else o)["platformFee"]=platform
            with self.subTest(target=target,platform=platform),patch.object(c,"get_order",side_effect=[q,o]),self.assertRaisesRegex(c.CaptureRejected,"PLATFORM_FEE_EVIDENCE_MISMATCH"):
                self.run_capture()

    def test_bounded_http_fixed_endpoint_and_sanitized_fields(self):
        response=Mock(status_code=200)
        response.iter_content.return_value=[json.dumps({"inAmount":"1000000","requestId":"discard","unknown":"discard"}).encode()]
        get=Mock(return_value=response)
        result=c.get_order({},"secret",get)
        self.assertEqual(result,{"inAmount":"1000000"})
        self.assertEqual(get.call_args.args[0],c.ENDPOINT)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        response.close.assert_called_once()

    def test_http_errors_duplicates_and_oversize_never_echo_secret(self):
        for status,raw in ((302,b""),(200,b'{"inAmount":"1","inAmount":"2"}'),(200,b"x"*(c.MAX_BYTES+1))):
            response=Mock(status_code=status);response.iter_content.return_value=[raw]
            with self.assertRaises(c.CaptureRejected): c.get_order({},"secret",Mock(return_value=response))
            response.close.assert_called_once()
        with self.assertRaisesRegex(c.CaptureRejected,"^JUPITER_CAPTURE_UNAVAILABLE$"):
            c.get_order({},"secret",Mock(side_effect=RuntimeError("secret")))

    def test_input_and_slippage_bounds(self):
        for value,slippage in (("1",50),("1000000001",50),("1000000",101)):
            with self.subTest(value=value,slippage=slippage),self.assertRaises(c.CaptureRejected):
                c.capture(WALLET,value,50,slippage,environment=env())
        self.verifier.assert_not_called()
