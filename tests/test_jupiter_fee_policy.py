"""Phase 03-C: real policy code, mocked upstream; no mainnet transactions."""

import base64
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import Mock, patch

from application.jupiter_fee_policy import (
    FeePolicy, FeePolicyConfigurationError, FeePolicyRejected,
    WSOL_MINT, USDC_MINT, get_fee_policy, read_fee_policy,
    valid_public_key, validate_fee_response,
    require_fee_execution_ready,
)


REFERRAL = "5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
ENV = {
    "DEXSATO_JUPITER_FEE_ENABLED": "true",
    "DEXSATO_JUPITER_REFERRAL_ACCOUNT": REFERRAL,
    "DEXSATO_JUPITER_REFERRAL_FEE_BPS": "50",
}


class FeePolicyTests(unittest.TestCase):
    def tearDown(self):
        get_fee_policy.cache_clear()

    def test_default_disabled_without_credentials(self):
        policy = read_fee_policy({})
        self.assertEqual(policy, FeePolicy())
        self.assertEqual(policy.request_parameters(), {})

    def test_disabled_ignores_dormant_example_values(self):
        self.assertEqual(read_fee_policy({**ENV, "DEXSATO_JUPITER_FEE_ENABLED": "false"}), FeePolicy())

    def test_malformed_flags_fail_closed(self):
        for flag in ("", "1", "0", "yes", "enabled", "tru"):
            with self.subTest(flag=flag), self.assertRaises(FeePolicyConfigurationError):
                read_fee_policy({**ENV, "DEXSATO_JUPITER_FEE_ENABLED": flag})

    def test_bps_bounds(self):
        for bps in ("50", "255"):
            with self.subTest(bps=bps):
                self.assertEqual(read_fee_policy({**ENV, "DEXSATO_JUPITER_REFERRAL_FEE_BPS": bps}).fee_bps, int(bps))
        for bps in ("", "0", "20", "49", "256", "-50", "50.1", "5e1", "NaN", "true", "５０"):
            with self.subTest(bps=bps), self.assertRaises(FeePolicyConfigurationError):
                read_fee_policy({**ENV, "DEXSATO_JUPITER_REFERRAL_FEE_BPS": bps})

    def test_account_requires_exact_base58_32_bytes(self):
        self.assertTrue(valid_public_key(REFERRAL))
        for value in ("", "3" * 32, "1" * 32, "secret", WSOL_MINT, USDC_MINT):
            with self.subTest(value=value), self.assertRaises(FeePolicyConfigurationError):
                read_fee_policy({**ENV, "DEXSATO_JUPITER_REFERRAL_ACCOUNT": value})

    def test_bad_configuration_never_echoes_value(self):
        secret = "accidentally-pasted-private-material"
        try:
            read_fee_policy({**ENV, "DEXSATO_JUPITER_REFERRAL_ACCOUNT": secret})
        except FeePolicyConfigurationError as error:
            self.assertNotIn(secret, str(error))
        else:
            self.fail("Expected configuration rejection")

    def test_policy_frozen_and_stable_for_process(self):
        with patch.dict(os.environ, ENV, clear=True):
            get_fee_policy.cache_clear()
            first = get_fee_policy()
            os.environ["DEXSATO_JUPITER_REFERRAL_FEE_BPS"] = "60"
            self.assertIs(get_fee_policy(), first)
            self.assertEqual(get_fee_policy().fee_bps, 50)
        with self.assertRaises(FrozenInstanceError):
            first.fee_bps = 60

    def test_exact_request_parameters_and_fingerprint(self):
        policy = read_fee_policy(ENV)
        self.assertEqual(policy.request_parameters(), {"referralAccount": REFERRAL, "referralFee": "50"})
        self.assertNotEqual(policy.fingerprint, FeePolicy().fingerprint)
        self.assertNotEqual(policy.fingerprint, FeePolicy(True, REFERRAL, 51).fingerprint)

    def test_execution_gate_cannot_be_opened_by_fee_flag(self):
        require_fee_execution_ready(FeePolicy())
        with self.assertRaises(FeePolicyConfigurationError):
            require_fee_execution_ready(read_fee_policy(ENV))

    def test_success_does_not_invent_amount_or_onchain_verification(self):
        evidence = validate_fee_response(read_fee_policy(ENV), {
            "referralAccount": REFERRAL, "feeBps": 50, "feeMint": WSOL_MINT,
            "platformFee": {"amount": "100", "feeBps": 10},
        }, input_mint=WSOL_MINT, output_mint=USDC_MINT)
        fields = evidence.public_fields()
        self.assertEqual(fields["dexsato_integrator_fee_status"], "PROVIDER_VALIDATED")
        self.assertEqual(fields["dexsato_referral_account"], REFERRAL)
        self.assertIsNone(fields["dexsato_fee_amount_raw"])

    def test_response_missing_malformed_mismatched_fields_rejected(self):
        good = {"referralAccount": REFERRAL, "feeBps": 50, "feeMint": WSOL_MINT}
        changes = [
            {"referralAccount": None}, {"referralAccount": USDC_MINT},
            {"feeBps": None}, {"feeBps": 5}, {"feeBps": 0}, {"feeBps": 51},
            {"feeBps": True}, {"feeBps": 50.5}, {"feeMint": None},
            {"feeMint": {}}, {"feeMint": REFERRAL}, {"feeMint": USDC_MINT},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(FeePolicyRejected):
                validate_fee_response(read_fee_policy(ENV), {**good, **change},
                                      input_mint=WSOL_MINT, output_mint=USDC_MINT)

    def test_disabled_allows_jupiter_fee_but_not_referral(self):
        result = validate_fee_response(FeePolicy(), {"feeBps": 50}, input_mint=WSOL_MINT, output_mint=USDC_MINT)
        self.assertEqual(result.public_fields()["dexsato_integrator_fee_bps"], 0)
        with self.assertRaises(FeePolicyRejected):
            validate_fee_response(FeePolicy(), {"referralAccount": REFERRAL},
                                  input_mint=WSOL_MINT, output_mint=USDC_MINT)


class FeeServiceTests(unittest.TestCase):
    def setUp(self):
        from application import jupiter_quote_service as quote
        from application import jupiter_swap_service as swap
        self.quote, self.swap = quote, swap
        self.environment = patch.dict(os.environ, ENV, clear=True)
        self.environment.start()
        # Exercise the dormant order pipeline with mocked upstream responses.
        # Production retains this gate until UI/on-chain validation is completed.
        self.execution_gate = patch("application.jupiter_swap_service.require_fee_execution_ready")
        self.execution_gate.start()
        get_fee_policy.cache_clear()
        swap._pending_orders.clear()
        self.now = datetime(2026, 8, 31, tzinfo=timezone.utc)
        self.wallet = "11111111111111111111111111111111"
        self.feed = {"candidates": [{"token_address": USDC_MINT}]}

    def tearDown(self):
        self.swap._pending_orders.clear()
        get_fee_policy.cache_clear()
        self.environment.stop()
        self.execution_gate.stop()

    def transaction(self, signed=False):
        # Synthetic Solana transaction fixture, never submitted to a network.
        message = (bytes([128, 1, 0, 1, 2]) + bytes(32)
                   + self.swap._base58_bytes(self.swap.JUPITER_V6_PROGRAM)
                   + bytes([6]) * 32 + bytes([1, 1, 1, 0, 1, 1, 0]))
        return base64.b64encode(bytes([1]) + bytes([1 if signed else 0]) * 64 + message).decode()

    def payload(self, **changes):
        result = {
            "inputMint": WSOL_MINT, "outputMint": USDC_MINT,
            "inAmount": "100000000", "outAmount": "2500000", "outputDecimals": 6,
            "referralAccount": REFERRAL, "feeBps": 50, "feeMint": WSOL_MINT,
            "requestId": "fee-test-order", "taker": self.wallet,
            "transaction": self.transaction(), "lastValidBlockHeight": "12345",
        }
        result.update(changes)
        return result

    def upstream(self, payload):
        response = Mock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return Mock(return_value=response)

    def prepare(self, **changes):
        self.request_get = self.upstream(self.payload(**changes))
        return self.swap.prepare_jupiter_swap(
            USDC_MINT, "0.1", self.wallet, risk_acknowledged=True, api_key="test-key",
            feed=self.feed, request_get=self.request_get, now=lambda: self.now,
        )

    def execute(self, response):
        self.request_post = self.upstream(response)
        return self.swap.execute_jupiter_swap(
            USDC_MINT, "fee-test-order", self.wallet, self.transaction(signed=True),
            api_key="test-key", feed=self.feed, request_post=self.request_post, now=lambda: self.now,
        )

    def test_quote_and_order_use_same_server_policy(self):
        upstream = self.upstream(self.payload(transaction=None))
        quote = self.quote.fetch_jupiter_quote(
            USDC_MINT, "0.1", api_key="test-key", feed=self.feed, request_get=upstream,
        )
        order = self.prepare()
        for key in ("referralAccount", "referralFee"):
            self.assertEqual(upstream.call_args.kwargs["params"][key], self.request_get.call_args.kwargs["params"][key])
        self.assertNotIn("taker", upstream.call_args.kwargs["params"])
        self.assertEqual(quote["dexsato_fee_policy_id"], order["dexsato_fee_policy_id"])
        self.assertEqual(order["dexsato_integrator_fee_bps"], 50)
        self.assertEqual(self.swap._pending_orders["fee-test-order"].fee_evidence.fee_mint, WSOL_MINT)

    def test_invalid_config_stops_before_upstream(self):
        os.environ["DEXSATO_JUPITER_REFERRAL_FEE_BPS"] = "20"
        with self.assertRaises(self.quote.JupiterQuoteNotConfigured):
            self.prepare()
        self.request_get.assert_not_called()

    def test_real_activation_gate_rejects_fee_order_before_network(self):
        self.execution_gate.stop()
        with self.assertRaises(self.quote.JupiterQuoteNotConfigured):
            self.prepare()
        self.request_get.assert_not_called()
        self.assertEqual(self.swap._pending_orders, {})

    def test_bad_quote_referral_is_not_returned(self):
        upstream = self.upstream(self.payload(transaction=None, referralAccount="wrong"))
        with self.assertRaises(self.quote.JupiterQuoteUnavailable):
            self.quote.fetch_jupiter_quote(USDC_MINT, "0.1", api_key="test-key", feed=self.feed, request_get=upstream)

    def test_bad_order_referral_creates_no_pending_order(self):
        for changes in ({"referralAccount": "wrong"}, {"feeBps": 5}, {"feeMint": None}):
            with self.subTest(changes=changes), self.assertRaises(self.quote.JupiterQuoteUnavailable):
                self.prepare(**changes)
        self.assertEqual(self.swap._pending_orders, {})

    def test_execute_uses_bound_fee_and_never_sends_fee_parameters(self):
        self.prepare()
        result = self.execute({"status": "Success", "signature": "55555"})
        self.assertEqual(result["dexsato_integrator_fee_bps"], 50)
        self.assertEqual(result["dexsato_referral_account"], REFERRAL)
        body = self.request_post.call_args.kwargs["json"]
        self.assertEqual(set(body), {"signedTransaction", "requestId", "lastValidBlockHeight"})

    def test_failed_execution_retains_bound_fee_without_claiming_receipt(self):
        self.prepare()
        result = self.execute({"status": "Failed", "error": "Swap failed"})
        self.assertEqual(result["dexsato_integrator_fee_bps"], 50)
        self.assertEqual(result["dexsato_integrator_fee_status"], "PROVIDER_VALIDATED")
        self.assertIsNone(result["dexsato_fee_amount_raw"])

    def test_execute_rejects_changed_policy_before_network(self):
        self.prepare()
        with patch("application.jupiter_swap_service._fee_policy", return_value=FeePolicy()):
            with self.assertRaises(self.swap.JupiterSwapRejected):
                self.execute({"status": "Success", "signature": "55555"})
        self.request_post.assert_not_called()

    def test_disabled_quote_and_order_remain_zero_fee(self):
        os.environ["DEXSATO_JUPITER_FEE_ENABLED"] = "false"
        order = self.prepare(referralAccount=None, feeBps=10, feeMint=WSOL_MINT)
        self.assertEqual(order["dexsato_integrator_fee_bps"], 0)
        self.assertNotIn("referralFee", self.request_get.call_args.kwargs["params"])


if __name__ == "__main__":
    unittest.main()
