"""Offline synthetic diagnostics. A passed test does NOT authorize a trade."""
import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from application import jupiter_fee_transaction_harness as h
from application.jupiter_fee_policy import FeePolicy, USDC_MINT, WSOL_MINT, require_fee_execution_ready, FeePolicyConfigurationError
from application.jupiter_swap_service import JUPITER_V6_PROGRAM, _base58_bytes

REFERRAL = "5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
WALLET = "J2PVpmi95iS5xyCoDMQXjWLCbZXHymU9nobxdQqwbVTs"
ATA = "3vDQ2eA5mAu1Wf5podZ7rFRnamuMKC9prhaTkf8PvyUv"


def transaction(signed=False, extra=False, lookup=False):
    keys = [WALLET, JUPITER_V6_PROGRAM, ATA]
    signers = 2 if extra else 1
    message = bytes([128, signers, 0, 1, 3]) + b"".join(_base58_bytes(k) for k in keys) + bytes([7])*32
    message += bytes([1, 1, 2, 0, 3 if lookup else 2, 1, 1])
    message += (bytes([1]) + bytes([9])*32 + bytes([1, 0, 0])) if lookup else bytes([0])
    return base64.b64encode(bytes([signers]) + bytes([1 if signed else 0])*(64*signers) + message).decode()


def evidence():
    quote = dict(inputMint=WSOL_MINT, outputMint=USDC_MINT, inAmount="1000000", outAmount="150000", otherAmountThreshold="140000", referralAccount=REFERRAL, feeBps=50, feeMint=WSOL_MINT)
    return quote, dict(quote, taker=WALLET, transaction=transaction())


class FeeHarnessTests(unittest.TestCase):
    def setUp(self):
        self.intent = h.Intent(WALLET, USDC_MINT, "1000000", "140000")
        self.policy = FeePolicy(True, REFERRAL, 50)
        mock = patch.object(h, "referral_token_address", return_value=ATA)
        mock.start(); self.addCleanup(mock.stop)

    def inspect(self, quote=None, order=None):
        q, o = evidence()
        return h.inspect_evidence(self.intent, self.policy, q if quote is None else quote, o if order is None else order)

    def test_structural_pass_never_authorizes_fee_execution(self):
        report = self.inspect()
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertTrue(report["expected_ata_in_static_accounts"])
        self.assertFalse(report["execution_ready"])
        self.assertFalse(report["transaction_fee_verified"])
        self.assertFalse(report["fee_receipt_verified"])
        with self.assertRaises(FeePolicyConfigurationError):
            require_fee_execution_ready(self.policy)

    def test_metadata_mismatches_rejected(self):
        changes = {"inputMint": USDC_MINT, "outputMint": WSOL_MINT, "inAmount": "1", "referralAccount": WALLET, "feeBps": 51, "feeMint": USDC_MINT, "gasless": True, "otherAmountThreshold": "139999"}
        for key, value in changes.items():
            for side in (0, 1):
                with self.subTest(key=key, side=side):
                    pair = list(evidence()); pair[side][key] = value
                    with self.assertRaises(h.HarnessRejected):
                        self.inspect(*pair)

    def test_bad_amounts_rejected(self):
        for raw in (True, 1, "0", "01", "-1", "1.0", "1e6", "18446744073709551616", None):
            with self.subTest(raw=raw), self.assertRaises(h.HarnessRejected):
                h.amount(raw)

    def test_signed_extra_signer_and_lookup_evidence_rejected(self):
        for kwargs in ({"signed": True}, {"extra": True}, {"lookup": True}):
            with self.subTest(kwargs=kwargs):
                q, o = evidence(); o["transaction"] = transaction(**kwargs)
                with self.assertRaises(h.HarnessRejected):
                    self.inspect(q, o)

    def test_wrong_taker_and_transaction_in_quote_rejected(self):
        q, o = evidence(); o["taker"] = REFERRAL
        with self.assertRaises(h.HarnessRejected): self.inspect(q, o)
        q, o = evidence(); q["transaction"] = transaction()
        with self.assertRaises(h.HarnessRejected): self.inspect(q, o)

    def test_malformed_transaction_rejected(self):
        for value in (None, "!", "AA==", "x"*9000):
            q, o = evidence(); o["transaction"] = value
            with self.assertRaises(h.HarnessRejected): self.inspect(q, o)

    def test_duplicate_and_oversized_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"evidence.json"
            for raw in (b'{"quote":{},"quote":{},"order":{}}', b"x"*(h.MAX_EVIDENCE_BYTES+1)):
                path.write_bytes(raw)
                with self.assertRaises(h.HarnessRejected): h.load_evidence(path)

    def test_cli_review_exit_is_nonzero_and_never_reports_raw_transaction(self):
        q, o = evidence()
        with patch.object(h, "load_evidence", return_value={"quote":q,"order":o}), patch("builtins.print") as output:
            result = h.main(["offline.json", "--wallet", WALLET, "--output-mint", USDC_MINT,
                "--input-raw", "1000000", "--minimum-output-raw", "140000",
                "--referral", REFERRAL, "--fee-bps", "50"])
        self.assertEqual(result, 2)
        self.assertNotIn(o["transaction"], output.call_args.args[0])
