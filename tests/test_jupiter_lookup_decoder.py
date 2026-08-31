import base64
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from application import jupiter_lookup_decoder as d
from application.jupiter_instruction_decoder import decode_route, inspect_transaction

ROUTE = bytes.fromhex("d19853937cfed8e90b40420f0000000000b9910100000000003200320000000400000026f206000100102701041101120c00041a0c140004")


def captured():
    return json.loads((Path(__file__).parent / "fixtures/jupiter_v2_unsigned.json").read_text())["transaction"]


def account(seed=1, count=256):
    # SYNTHETIC table addresses: never claim these resolve the captured mainnet accounts.
    raw = struct.pack("<IQQBB", 1, (1 << 64)-1, 5, 0, 0) + bytes(34)
    raw += b"".join(hashlib.sha256(bytes([seed, i])).digest() for i in range(count))
    return {"owner": d.ALT_PROGRAM, "executable": False, "data": [base64.b64encode(raw).decode(), "base64"]}


def snapshot(lookups):
    return {"context": {"slot": 100}, "value": [account(i+1) for i in range(len(lookups))]}


class LookupDecoderTests(unittest.TestCase):
    def test_captured_v2_header_and_remaining_roles(self):
        decoded = decode_route(ROUTE)
        args = decoded["args"]
        self.assertEqual((args["id"], args["inAmount"], args["quotedOutAmount"], args["platformFeeBps"]), (11, 1000000, 102841, 50))
        self.assertEqual(len(args["routePlan"]), 4)
        self.assertEqual(args["routePlan"][0]["swap"]["variant"], "MeteoraDlmm")
        self.assertEqual(len(decoded["account_roles"]), 12)
        self.assertNotIn("platformFeeAccount", decoded["account_roles"])

    def test_u16_fee_not_legacy_u8(self):
        data = bytearray(ROUTE)
        data[27:29] = struct.pack("<H", 300)
        self.assertEqual(decode_route(bytes(data))["args"]["platformFeeBps"], 300)

    def test_truncation_and_trailing_rejected(self):
        for length in range(len(ROUTE)):
            with self.subTest(length=length), self.assertRaises(d.DecodeRejected):
                decode_route(ROUTE[:length])
        with self.assertRaises(d.DecodeRejected): decode_route(ROUTE+b"\0")

    def test_unknown_enum_and_bad_bps_rejected(self):
        for offset, value in ((35, 255), (27, 255), (31, 255)):
            data = bytearray(ROUTE)
            data[offset] = value
            if offset == 27: data[28] = 255
            with self.assertRaises(d.DecodeRejected): decode_route(bytes(data))

    def test_captured_message_counts_and_hash(self):
        message, instructions, keys, lookups = d.message_layout(captured())
        self.assertEqual(hashlib.sha256(message).hexdigest(), "c8702ab8143a6f523dd349269db758fb43e6dec4aa94eb63a24caf0c50f3ac66")
        self.assertEqual((len(keys), len(lookups), len(instructions)), (19, 5, 8))
        self.assertEqual(sum(len(t["writable"]) for t in lookups), 16)
        self.assertEqual(sum(len(t["readonly"]) for t in lookups), 15)
        self.assertEqual(instructions[6].data, ROUTE)
        report = inspect_transaction(captured())
        self.assertEqual(report["instructions"][6]["status"], "LAYOUT_DECODED_LOOKUPS_UNRESOLVED")
        self.assertFalse(report["execution_ready"])

    def test_canonical_all_writable_before_all_readonly(self):
        lookups = [{"address": "table1", "writable": [1], "readonly": [0]},
                   {"address": "table2", "writable": [2], "readonly": [3]}]
        loaded, _, slot = d.resolve_snapshot(lookups, snapshot(lookups))
        self.assertEqual(slot, 100)
        self.assertEqual([(k["table"], k["table_index"], k["is_writable"]) for k in loaded],
            [("table1",1,True), ("table2",2,True), ("table1",0,False), ("table2",3,False)])
        self.assertTrue(all(not k["is_signer"] for k in loaded))

    def test_bad_rpc_context_and_missing_accounts(self):
        tables = [{"address": "table", "writable": [0], "readonly": []}]
        for value in (None, {}, {"context": {"slot": True}, "value": [account()]},
                      {"context": {"slot": 100}, "value": []}, {"context": {"slot": 100}, "value": [None]}):
            with self.subTest(value=value), self.assertRaises(d.DecodeRejected): d.resolve_snapshot(tables, value)

    def test_owner_encoding_and_executable(self):
        for key, value in (("owner", "wrong"), ("executable", True), ("data", ["!", "base64"]), ("data", ["", "jsonParsed"])):
            a = account(); a[key] = value
            with self.assertRaises(d.DecodeRejected): d.table_addresses(a, 100)

    def test_alt_metadata_size_and_state(self):
        original = base64.b64decode(account()["data"][0])
        mutations = [original[:55], original+b"x", bytes(4)+original[4:],
            original[:4]+bytes(8)+original[12:], original[:21]+b"\2"+original[22:]]
        for raw in mutations:
            a = account(); a["data"][0] = base64.b64encode(raw).decode()
            with self.subTest(size=len(raw)), self.assertRaises(d.DecodeRejected): d.table_addresses(a, 100)
        for slot in (True, 5, 4):
            with self.assertRaises(d.DecodeRejected): d.table_addresses(account(), slot)

    def test_lookup_index_bounds(self):
        tables = [{"address": "table", "writable": [2], "readonly": []}]
        with self.assertRaises(d.DecodeRejected):
            d.resolve_snapshot(tables, {"context": {"slot": 100}, "value": [account(count=2)]})

    def test_signed_capture_rejected_before_rpc(self):
        raw = bytearray(base64.b64decode(captured())); raw[1] = 1
        with patch.object(d, "_rpc") as rpc, self.assertRaises(d.DecodeRejected):
            d.inspect_resolved(base64.b64encode(raw).decode(), "https://rpc.example")
        rpc.assert_not_called()

    def test_bad_header_and_shortvec(self):
        raw = bytearray(base64.b64decode(captured())); raw[68] = 255
        with self.assertRaises(d.DecodeRejected): d.message_layout(base64.b64encode(raw).decode())
        for raw in (b"\x80\0", b"\xff\xff\xff"):
            with self.assertRaises(d.DecodeRejected): d.MessageReader(raw).short()

    def test_only_two_readonly_rpc_methods_and_report_stays_closed(self):
        _, _, _, lookups = d.message_layout(captured())
        with patch.object(d, "_rpc", side_effect=[d.MAINNET_GENESIS, snapshot(lookups)]) as rpc:
            report = d.inspect_resolved(captured(), "https://rpc.example")
        self.assertEqual([c.args[1] for c in rpc.call_args_list], ["getGenesisHash", "getMultipleAccounts"])
        self.assertEqual(report["account_count"], 50)
        self.assertEqual((report["loaded_writable_count"], report["loaded_readonly_count"]), (16,15))
        self.assertFalse(report["execution_ready"])
        self.assertFalse(report["transaction_fee_verified"])
        self.assertFalse(report["fee_receipt_verified"])
        route = report["instructions"][6]
        self.assertEqual(route["status"], "LAYOUT_DECODED_ACCOUNTS_RESOLVED")
        self.assertEqual(route["remaining_accounts"][0]["address"], "3vDQ2eA5mAu1Wf5podZ7rFRnamuMKC9prhaTkf8PvyUv")
        self.assertFalse(route["fee_account_role_verified"])

    def test_https_and_network_fail_closed(self):
        for url in ("http://rpc.example", "https://u:p@rpc.example", "https://rpc.example/#secret", ""):
            with patch.object(d, "_rpc") as rpc, self.assertRaises(d.DecodeRejected): d.inspect_resolved(captured(), url)
            rpc.assert_not_called()
        with patch.object(d, "_rpc", return_value="devnet") as rpc, self.assertRaises(d.DecodeRejected):
            d.inspect_resolved(captured(), "https://rpc.example")
        self.assertEqual(rpc.call_count, 1)

    def test_rpc_transport_is_bounded_and_redacted(self):
        class Response:
            status_code = 200
            closed = False
            def iter_content(self, chunk_size):
                yield b"x" * 131073
            def close(self): self.closed = True
        response = Response()
        def post(url, **kwargs):
            self.assertFalse(kwargs["allow_redirects"])
            self.assertTrue(kwargs["stream"])
            self.assertEqual(kwargs["timeout"], (3,8))
            return response
        with self.assertRaisesRegex(d.ReferralVerificationError, "^RPC_RESPONSE_TOO_LARGE$"):
            d.inspect_resolved(captured(), "https://rpc.example/?secret=hidden", request_post=post)
        self.assertTrue(response.closed)

    def test_cli_refuses_overwrite_and_fee_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/"evidence.json"
            source.write_text(json.dumps({"order": {"transaction": captured()}}))
            output = Path(directory)/"report.json"
            output.write_text("existing report")
            argv = ["decoder", "--evidence", str(source), "--output", str(output)]
            report = {"status": "RESOLVED_REVIEW_REQUIRED"}
            with patch("sys.argv", argv), patch.dict(d.os.environ, {"DEXSATO_JUPITER_FEE_ENABLED": "false"}), patch.object(d, "inspect_resolved", return_value=report):
                self.assertEqual(d.main(), 1)
            self.assertEqual(output.read_text(), "existing report")
            with patch("sys.argv", argv), patch.dict(d.os.environ, {"DEXSATO_JUPITER_FEE_ENABLED": "true"}), patch.object(d, "inspect_resolved") as resolver:
                self.assertEqual(d.main(), 1)
            resolver.assert_not_called()
