import base64
import hashlib
import runpy
import sys
import types
from pathlib import Path

from solders.message import MessageV0, to_bytes_versioned
from solders.instruction import CompiledInstruction
from solders.signature import Signature
from solders.transaction import VersionedTransaction

# Allow this standalone package test to load the decoder without importing the
# complete application graph. The installed project exercises the real modules.
if "application.jupiter_swap_service" not in sys.modules:
    swap_stub = types.ModuleType("application.jupiter_swap_service")
    swap_stub._transaction_parts = lambda _: None
    swap_stub._base58_text = lambda value: str(value)
    swap_stub.JUPITER_V6_PROGRAM = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
    class StubRejected(Exception): pass
    swap_stub.JupiterSwapRejected = StubRejected
    sys.modules["application.jupiter_swap_service"] = swap_stub
if "application.jupiter_referral_verification" not in sys.modules:
    referral_stub = types.ModuleType("application.jupiter_referral_verification")
    referral_stub._rpc = lambda *a, **k: None
    referral_stub.MAINNET_GENESIS = "mainnet"
    class StubReferralError(Exception): pass
    referral_stub.ReferralVerificationError = StubReferralError
    sys.modules["application.jupiter_referral_verification"] = referral_stub

from application.jupiter_lookup_decoder import decode_v2, ROUTE_V2_ROLES
from application.jupiter_order_identity_binding import audit_order_identity


REAL_ROUTE_V2_DATA = bytes.fromhex(
    "bb64facc31c4af1440420f0000000000d59401000000000032003200000001000000590110270001")


def test_captured_route_v2_header_is_decoded_without_guessing_new_route_enum():
    decoded = decode_v2(REAL_ROUTE_V2_DATA)
    assert decoded["name"] == "routeV2"
    assert decoded["args"]["inAmount"] == 1_000_000
    assert decoded["args"]["quotedOutAmount"] == 103_637
    assert decoded["args"]["slippageBps"] == 50
    assert decoded["args"]["platformFeeBps"] == 50
    assert decoded["args"]["routePlanCount"] == 1
    assert decoded["args"]["routePlan"] is None
    assert decoded["route_plan_decoded"] is False
    assert decoded["account_roles"] == ROUTE_V2_ROLES


def test_route_v2_identity_roles_bind_to_actual_transaction_bytes():
    helper = runpy.run_path(str(Path(__file__).with_name("test_jupiter_order_identity_binding.py")))
    encoded, order, expected, snapshot, _, slot = helper["sample"]()
    tx = VersionedTransaction.from_bytes(base64.b64decode(encoded))
    message = tx.message
    original = message.instructions[0]
    data = bytearray(bytes.fromhex("bb64facc31c4af14") + bytes(original.data)[9:])
    # RouteV2 fixed roles: authority, source, destination, source/destination
    # mint, source/destination token program, unverified fixed account, event,
    # program. Identity binding deliberately consumes only roles 0-6 and 9.
    roles = bytes([0, 1, 2, 11, 12, 3, 3, 5, 8, 4])
    instruction = CompiledInstruction(original.program_id_index, bytes(data), roles)
    message = MessageV0(message.header, message.account_keys, message.recent_blockhash,
                        [instruction], message.address_table_lookups)
    encoded = base64.b64encode(bytes(VersionedTransaction.populate(
        message, [Signature.default()]))).decode()
    digest = hashlib.sha256(to_bytes_versioned(message)).hexdigest()
    report = audit_order_identity(encoded, order, expected, snapshot, digest, slot)
    assert report["route_variant"] == "routeV2"
    assert report["identity_snapshot_consistent"] is True
    assert report["execution_ready"] is False
    assert report["enforced_minimum_raw"] is None


def test_shared_accounts_route_v2_remains_supported():
    helper = runpy.run_path(str(Path(__file__).with_name("test_jupiter_order_identity_binding.py")))
    report = audit_order_identity(*helper["sample"]())
    assert report["route_variant"] == "sharedAccountsRouteV2"
    assert report["identity_snapshot_consistent"] is True


def test_route_v2_rejects_unknown_discriminator_and_invalid_header_values():
    import pytest
    from application.jupiter_instruction_decoder import DecodeRejected
    with pytest.raises(DecodeRejected, match="INVALID_V2_DISCRIMINATOR_OR_SIZE"):
        decode_v2(bytes.fromhex("00" * 8) + REAL_ROUTE_V2_DATA[8:])
    malformed = bytearray(REAL_ROUTE_V2_DATA)
    malformed[24:26] = (10_001).to_bytes(2, "little")
    with pytest.raises(DecodeRejected, match="INVALID_V2_AMOUNTS_OR_BPS"):
        decode_v2(bytes(malformed))


def test_route_v2_rejects_empty_or_unbounded_route_plan():
    import pytest
    from application.jupiter_instruction_decoder import DecodeRejected
    empty = bytearray(REAL_ROUTE_V2_DATA)
    empty[30:34] = (0).to_bytes(4, "little")
    with pytest.raises(DecodeRejected, match="ROUTE_PLAN_LIMIT"):
        decode_v2(bytes(empty))
    excessive = bytearray(REAL_ROUTE_V2_DATA)
    excessive[30:34] = (65).to_bytes(4, "little")
    with pytest.raises(DecodeRejected, match="ROUTE_PLAN_LIMIT"):
        decode_v2(bytes(excessive))


def test_unverified_fixed_account_is_not_used_as_identity_evidence():
    assert ROUTE_V2_ROLES[7] == "unverifiedFixedAccount"
