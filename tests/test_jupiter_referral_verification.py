"""Synthetic account data only. No private keys or live RPC in tests."""
import base64
import copy
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from application import jupiter_referral_verification as v
from application.jupiter_fee_policy import WSOL_MINT, USDC_MINT, FeePolicy, FeeEvidence, FeePolicyRejected
from application.jupiter_fee_disclosure import build_fee_disclosure

REFERRAL = "5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ"
PARTNER = USDC_MINT  # Synthetic public-address fixture, NOT the user's owner.
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def raw_key(value):
    number = 0
    for ch in value:
        number = number * 58 + ALPHABET.index(ch)
    return b"\0" * (len(value) - len(value.lstrip("1"))) + number.to_bytes((number.bit_length()+7)//8, "big")


def account(raw, owner=v.REFERRAL_PROGRAM):
    return {"owner": owner, "executable": False, "data": [base64.b64encode(raw).decode(), "base64"]}


def anchor(name):
    return hashlib.sha256(("account:" + name).encode()).digest()[:8]


def fixtures():
    project = anchor("Project") + bytes([7])*32 + bytes([8])*32 + (5).to_bytes(4, "little") + b"Ultra" + (8000).to_bytes(2, "little")
    referral = anchor("ReferralAccount") + raw_key(PARTNER) + raw_key(v.ULTRA_PROJECT) + (8000).to_bytes(2, "little") + b"\1" + (7).to_bytes(4, "little") + b"DexSato"
    tokens = []
    for mint in (WSOL_MINT, USDC_MINT):
        raw = bytearray(165)
        raw[:32], raw[32:64], raw[108] = raw_key(mint), raw_key(REFERRAL), 1
        if mint == WSOL_MINT:
            raw[109:113] = (1).to_bytes(4, "little")
            raw[113:121] = (2039280).to_bytes(8, "little")
        tokens.append(account(raw, v.TOKEN_PROGRAM))
    return {"context": {"slot": 123456}, "value": [account(project), account(referral), *tokens]}


class ReferralVerificationTests(unittest.TestCase):
    def setUp(self):
        # Isolate byte-layout tests from SDK math; separate SDK test below.
        self.key = patch.object(v, "_pubkey", side_effect=raw_key)
        def fake_pda(seeds, program_id=v.REFERRAL_PROGRAM):
            if program_id == v.ASSOCIATED_TOKEN_PROGRAM:
                # Distinct synthetic addresses; real PDA math tested below.
                self.assertEqual(seeds[:2], [raw_key(REFERRAL), raw_key(v.TOKEN_PROGRAM)])
                return WSOL_MINT if seeds[2] == raw_key(WSOL_MINT) else USDC_MINT
            return v.ULTRA_PROJECT if seeds[0] == b"project" else REFERRAL
        self.pda = patch.object(v, "_pda", side_effect=fake_pda)
        self.key.start(); self.pda_mock = self.pda.start()
        self.addCleanup(self.key.stop); self.addCleanup(self.pda.stop)

    def validate(self, data):
        return v.validate_snapshot(REFERRAL, PARTNER, (WSOL_MINT, USDC_MINT), data)

    def test_valid_snapshot_is_account_evidence_not_fee_receipt(self):
        report = self.validate(fixtures()).public_fields()
        self.assertEqual(report["status"], "RPC_ACCOUNT_VERIFIED")
        self.assertEqual(report["partner_share_bps"], 8000)
        self.assertFalse(report["fee_receipt_verified"])
        self.assertEqual(report["slot"], 123456)
        self.assertEqual(report["token_account_model"], "ULTRA_V2_ATA")
        self.assertEqual(report["token_authority"], REFERRAL)

    def test_rejects_identity_layout_share_and_token_mutations(self):
        # Offset tests directly exercise the official Borsh/SPL layouts.
        changes = [(0, 0), (1, 0), (1, 8), (1, 40), (1, 72), (1, 74),
                   (2, 0), (2, 32), (2, 108), (2, 72), (2, 129), (2, 121), (2, 109), (3, 109)]
        for index, offset in changes:
            with self.subTest(index=index, offset=offset):
                data = fixtures()
                raw = bytearray(base64.b64decode(data["value"][index]["data"][0]))
                raw[offset] ^= 255
                data["value"][index]["data"][0] = base64.b64encode(raw).decode()
                with self.assertRaises(v.ReferralVerificationError):
                    self.validate(data)

    def test_rejects_missing_wrong_owner_executable_and_truncated(self):
        for index in range(4):
            for mutation in (None, {"owner": WSOL_MINT}, {"executable": True}, {"data": ["AA==", "base64"]}, {"data": ["!", "base64"]}):
                with self.subTest(index=index, mutation=mutation):
                    data = fixtures()
                    if mutation is None:
                        data["value"][index] = None
                    else:
                        data["value"][index].update(mutation)
                    with self.assertRaises(v.ReferralVerificationError):
                        self.validate(data)

    def test_rejects_bad_slot_count_mints_and_project_pda(self):
        for result in ({}, {"context": {"slot": True}, "value": []}, {"context": {"slot": 10}, "value": [None]}):
            with self.assertRaises(v.ReferralVerificationError):
                self.validate(result)
        with patch.object(v, "_pda", return_value=REFERRAL), self.assertRaisesRegex(v.ReferralVerificationError, "PROJECT_PDA"):
            self.validate(fixtures())
        with self.assertRaises(v.ReferralVerificationError):
            v.validate_snapshot(REFERRAL, PARTNER, (WSOL_MINT, WSOL_MINT), fixtures())

    def test_named_referral_uses_project_name_seed(self):
        data = fixtures()
        raw = base64.b64decode(data["value"][1]["data"][0])[:74]
        data["value"][1] = account(raw + b"\1" + (7).to_bytes(4, "little") + b"DexSato")
        self.validate(data)
        self.pda_mock.assert_any_call([b"referral", raw_key(v.ULTRA_PROJECT), b"DexSato"])

    def test_unnamed_referral_rejected_by_v2_claim_contract(self):
        data = fixtures()
        raw = base64.b64decode(data["value"][1]["data"][0])[:74]
        data["value"][1] = account(raw + b"\0")
        with self.assertRaisesRegex(v.ReferralVerificationError, "ULTRA_V2_REQUIRES_NAMED_REFERRAL"):
            self.validate(data)

    def test_project_and_partner_authority_are_not_v2_referral_authority(self):
        for authority in (v.ULTRA_PROJECT, PARTNER):
            for index in (2, 3):
                with self.subTest(authority=authority, index=index):
                    data = fixtures()
                    raw = bytearray(base64.b64decode(data["value"][index]["data"][0]))
                    raw[32:64] = raw_key(authority)
                    data["value"][index] = account(raw, v.TOKEN_PROGRAM)
                    with self.assertRaisesRegex(v.ReferralVerificationError, "TOKEN_MINT_OR_AUTHORITY_MISMATCH"):
                        self.validate(data)

    def test_missing_v2_account_does_not_fallback_to_v1(self):
        data = fixtures()
        data["value"][2] = None
        with patch.object(v, "_rpc", side_effect=[v.MAINNET_GENESIS, data]) as rpc:
            with self.assertRaisesRegex(v.ReferralVerificationError, "MISSING_REFERRAL_TOKEN_ACCOUNT_WSOL"):
                v.verify_referral_accounts(REFERRAL, PARTNER, rpc_url="https://rpc.example")
        self.assertEqual(rpc.call_count, 2)
        self.assertEqual(rpc.call_args.args[2][0], [v.ULTRA_PROJECT, REFERRAL, WSOL_MINT, USDC_MINT])

    def test_rpc_read_only_mainnet_finalized_and_no_secret_output(self):
        def response(result):
            res = Mock(status_code=200)
            res.iter_content.return_value = [json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()]
            return res
        post = Mock(side_effect=[response(v.MAINNET_GENESIS), response(fixtures())])
        report = v.verify_referral_accounts(REFERRAL, PARTNER, rpc_url="https://rpc.example/?key=secret", request_post=post)
        calls = post.call_args_list
        self.assertEqual([c.kwargs["json"]["method"] for c in calls], ["getGenesisHash", "getMultipleAccounts"])
        self.assertEqual(calls[1].kwargs["json"]["params"][1]["commitment"], "finalized")
        self.assertEqual(calls[1].kwargs["json"]["params"][0], [v.ULTRA_PROJECT, REFERRAL, WSOL_MINT, USDC_MINT])
        self.assertFalse(calls[0].kwargs["allow_redirects"])
        self.assertNotIn("secret", json.dumps(report.public_fields()))
        bad = Mock(side_effect=RuntimeError("https://rpc.example/?key=secret"))
        with self.assertRaisesRegex(v.ReferralVerificationError, "^RPC_UNAVAILABLE$"):
            v.verify_referral_accounts(REFERRAL, PARTNER, rpc_url="https://rpc.example", request_post=bad)

    def test_configuration_and_wrong_network_stop_before_account_fetch(self):
        post = Mock()
        for endpoint in ("", "http://rpc.example", "https://user:secret@rpc.example", "https://rpc.example/#fragment"):
            with patch.dict("os.environ", {}, clear=True), self.assertRaises(v.ReferralVerificationError):
                v.verify_referral_accounts(REFERRAL, PARTNER, rpc_url=endpoint, request_post=post)
        post.assert_not_called()
        for genesis in ("devnet", "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"):
            with patch.object(v, "_rpc", return_value=genesis) as rpc, self.assertRaisesRegex(v.ReferralVerificationError, "NOT_SOLANA_MAINNET"):
                v.verify_referral_accounts(REFERRAL, PARTNER, rpc_url="https://rpc.example")
            self.assertEqual(rpc.call_count, 1)

    def test_rpc_limits_invalid_envelopes_and_closes_response(self):
        payloads = [b"!", b"x"*(v.MAX_RPC_BYTES+1), b'{"jsonrpc":"2.0","id":true,"result":{}}', b'{"jsonrpc":"2.0","id":1,"error":{}}']
        for payload in payloads:
            response = Mock(status_code=200)
            response.iter_content.return_value = [payload]
            with self.assertRaises(v.ReferralVerificationError):
                v._rpc("https://rpc.example", "getGenesisHash", [], Mock(return_value=response))
            response.close.assert_called_once()


class ReferralSDKTests(unittest.TestCase):
    def test_solders_derives_canonical_v2_atas_not_legacy_v1_pdas(self):
        from solders.pubkey import Pubkey
        for mint in (WSOL_MINT, USDC_MINT):
            address = v.referral_token_address(REFERRAL, mint)
            expected, bump = Pubkey.find_program_address([bytes(Pubkey.from_string(REFERRAL)), bytes(Pubkey.from_string(v.TOKEN_PROGRAM)), bytes(Pubkey.from_string(mint))], Pubkey.from_string(v.ASSOCIATED_TOKEN_PROGRAM))
            legacy, _ = Pubkey.find_program_address([b"referral_ata", bytes(Pubkey.from_string(REFERRAL)), bytes(Pubkey.from_string(mint))], Pubkey.from_string(v.REFERRAL_PROGRAM))
            self.assertEqual(address, str(expected))
            self.assertNotEqual(address, str(legacy))
            self.assertFalse(expected.is_on_curve())
            self.assertGreaterEqual(bump, 0)


class FeeDisclosureTests(unittest.TestCase):
    def test_disabled_does_not_require_rpc_or_fabricate_zero_jupiter_fee(self):
        with patch("application.jupiter_fee_disclosure.verify_referral_accounts") as rpc:
            result = build_fee_disclosure(FeeEvidence(FeePolicy()), {}, 100000000)
        rpc.assert_not_called()
        self.assertEqual(result["integrator_fee_amount_ui"], "0")
        self.assertIn("Jupiter route fees may still apply", result["note"])
        self.assertTrue(result["execution_ready"])

    def test_enabled_estimate_includes_share_not_added_twice(self):
        evidence = FeeEvidence(FeePolicy(True, REFERRAL, 50), WSOL_MINT)
        report = v.ReferralObservation(REFERRAL, PARTNER, 8000, 123, "now", ())
        with patch("application.jupiter_fee_disclosure.verify_referral_accounts", return_value=report):
            result = build_fee_disclosure(evidence, {"inAmount": "100000000"}, 100000000)
        self.assertEqual(result["integrator_fee_amount_ui"], "0.0005")
        self.assertEqual(result["jupiter_share_percent"], "20.00")
        self.assertEqual(result["amount_kind"], "ESTIMATE")
        self.assertFalse(result["execution_ready"])
        self.assertFalse(result["fee_receipt_verified"])

    def test_enabled_rejects_missing_input_gasless_and_verification_failure(self):
        evidence = FeeEvidence(FeePolicy(True, REFERRAL, 50), WSOL_MINT)
        for payload in ({}, {"inAmount": "1"}, {"inAmount": "100000000", "gasless": True}):
            with self.assertRaises(FeePolicyRejected):
                build_fee_disclosure(evidence, payload, 100000000)
        with patch("application.jupiter_fee_disclosure.verify_referral_accounts", side_effect=v.ReferralVerificationError("MISSING_ACCOUNT")):
            with self.assertRaises(v.ReferralVerificationError):
                build_fee_disclosure(evidence, {"inAmount": "100000000"}, 100000000)
