import hashlib
import struct
import unittest
from unittest.mock import patch
from application import jupiter_instruction_decoder as d
from application.jupiter_swap_service import _CompiledInstruction, _base58_bytes, JUPITER_V6_PROGRAM


def route(shared=False, swap=7, fields=b""):
    name = "shared_accounts_route" if shared else "route"
    # Raydium is enum 7, Whirlpool 17 has a bool; fields precede percent/indexes.
    return hashlib.sha256(("global:"+name).encode()).digest()[:8] + (b"\0" if shared else b"") + struct.pack("<I",1) + bytes([swap]) + fields + bytes([100,0,1]) + struct.pack("<QQHB",1000000,150000,50,50)


class InstructionDecoderTests(unittest.TestCase):
    def test_route_and_shared_exactin_fields(self):
        for shared in (False,True):
            with self.subTest(shared=shared):
                report=d.decode_route(route(shared))
                self.assertEqual(report["args"]["inAmount"],1000000)
                self.assertEqual(report["args"]["quotedOutAmount"],150000)
                self.assertEqual(report["args"]["platformFeeBps"],50)
                self.assertEqual(report["args"]["routePlan"][0]["swap"]["variant"],"Raydium")
                self.assertEqual(report["account_roles"][9 if shared else 6],"platformFeeAccount")

    def test_variable_length_swap_fields_not_suffix_guessing(self):
        result=d.decode_route(route(swap=17,fields=b"\1"))
        self.assertTrue(result["args"]["routePlan"][0]["swap"]["fields"]["aToB"])
        result=d.decode_route(route(swap=29,fields=struct.pack("<QQ",11,22)))
        self.assertEqual(result["args"]["routePlan"][0]["swap"]["fields"]["toTokenId"],22)

    def test_unknown_discriminator_and_enum_rejected(self):
        for value in (bytes(8)+route()[8:],route(swap=255)):
            with self.assertRaises(d.DecodeRejected): d.decode_route(value)

    def test_truncated_and_trailing_bytes_rejected(self):
        data=route()
        for length in range(len(data)):
            with self.subTest(length=length),self.assertRaises(d.DecodeRejected): d.decode_route(data[:length])
        with self.assertRaises(d.DecodeRejected): d.decode_route(data+b"\0")

    def test_bad_boolean_and_vector_count_rejected(self):
        for value in (route(swap=17,fields=b"\2"),route()[:8]+struct.pack("<I",65)+route()[12:]):
            with self.assertRaises(d.DecodeRejected): d.decode_route(value)

    def test_account_roles_unresolved_not_approved(self):
        keys=[_base58_bytes(JUPITER_V6_PROGRAM)]
        ix=_CompiledInstruction(0,tuple(range(9)),route())
        parts=(b"",[bytes(64)],b"message",keys,keys,[ix])
        with patch.object(d,"_transaction_parts",return_value=parts):
            report=d.inspect_transaction("synthetic")
        self.assertFalse(report["execution_ready"])
        self.assertEqual(report["instructions"][0]["status"],"LAYOUT_DECODED_LOOKUPS_UNRESOLVED")
        self.assertIsNone(report["instructions"][0]["accounts"]["platformFeeAccount"]["address"])

    def test_unknown_instruction_report_stays_blocked(self):
        keys=[_base58_bytes(JUPITER_V6_PROGRAM)]
        parts=(b"",[bytes(64)],b"message",keys,keys,[_CompiledInstruction(0,(0,),bytes(8))])
        with patch.object(d,"_transaction_parts",return_value=parts): report=d.inspect_transaction("synthetic")
        self.assertFalse(report["transaction_fee_verified"])
        self.assertEqual(report["instructions"][0]["reason"],"UNSUPPORTED_JUPITER_DISCRIMINATOR")
