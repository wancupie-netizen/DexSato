import hashlib
import inspect
from datetime import datetime, timezone

import pytest

from application import jupiter_claim_v2_wallet_boundary as boundary
from application.jupiter_claim_v2_gate_design import CONFIRMATION_PHRASE
from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, arm_claim_gate, read_gate,
)

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
WALLET = "wallet"
UNSIGNED_RAW = b"unsigned-transaction"
MESSAGE = b"claim-v2-message"
UNSIGNED_HASH = hashlib.sha256(UNSIGNED_RAW).hexdigest()
MESSAGE_HASH = hashlib.sha256(MESSAGE).hexdigest()
DEFAULT = bytes(64)
SIGNED_RAW = b"signed-transaction"


def closure():
    return {"status": "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED",
        "closure_id": "c" * 64, "message_sha256": MESSAGE_HASH,
        "transaction_sha256": UNSIGNED_HASH, "mint": "mint",
        "referral_account": "referral", "partner": WALLET,
        "gross_claim_raw": "5000", "partner_delta_raw": "4000",
        "project_admin_delta_raw": "1000",
        "claim_gate_design_eligible": True,
        "simulated_claim_split_verified": True,
        "balance_conservation_verified": True,
        "claim_execution_approved": False, "transaction_signed": False,
        "transaction_submitted": False, "claim_submitted": False,
        "execution_ready": False}


def capture():
    return {"status": "SDK_UNSIGNED_CAPTURED", "transaction": "unsigned",
        "message_sha256": MESSAGE_HASH, "transaction_sha256": UNSIGNED_HASH,
        "identity": {"payer": WALLET, "partner": WALLET},
        "execution_ready": False, "fee_receipt_verified": False}


def parser(value):
    if value == "unsigned":
        return {"raw": UNSIGNED_RAW, "message": MESSAGE,
            "required_signers": [WALLET], "signatures": [DEFAULT],
            "default_signature": DEFAULT}
    if value == "signed":
        return {"raw": SIGNED_RAW, "message": MESSAGE,
            "required_signers": [WALLET], "signatures": [b"s" * 64],
            "default_signature": DEFAULT}
    raise AssertionError("unexpected test transaction")


def armed(tmp_path):
    path = tmp_path / "gate.json"
    arm_claim_gate(path, closure(), CONFIRMATION_PHRASE,
        environment={"DEXSATO_JUPITER_CLAIM_GATE_ENABLED": "true",
                     "DEXSATO_JUPITER_FEE_ENABLED": "false"}, current=NOW)
    return path


def test_exact_wallet_signature_binds_digest_without_persisting_transaction(tmp_path):
    path = armed(tmp_path)
    report = boundary.validate_wallet_signed_claim(
        path, closure(), capture(), "signed", WALLET,
        current=NOW, decoder=parser)
    assert report["status"] == "CLAIM_V2_WALLET_APPROVAL_BOUND_REVIEW_REQUIRED"
    assert report["wallet_signature_verified"] is True
    assert report["signed_transaction_sha256"] == hashlib.sha256(SIGNED_RAW).hexdigest()
    assert report["signed_transaction_persisted"] is False
    assert report["submission_attempt_count"] == 0
    assert report["submission_permitted"] is False
    assert report["claim_submitted"] is False
    assert report["live_claim_approved"] is False
    assert report["claim_execution_ready"] is False
    assert report["execution_ready"] is False
    stored = read_gate(path)
    assert "transaction" not in stored and "signed_transaction" not in stored


@pytest.mark.parametrize("mutation,code", [
    ({"message": b"changed"}, "WALLET_SIGNED_MESSAGE_CHANGED"),
    ({"required_signers": ["other"]}, "WALLET_SIGNER_SET_MISMATCH"),
    ({"signatures": [DEFAULT]}, "WALLET_SIGNATURE_MISSING"),
])
def test_message_signer_and_signature_mutations_fail_closed(tmp_path, mutation, code):
    path = armed(tmp_path)
    def changed(value):
        result = parser(value)
        if value == "signed":
            result = {**result, **mutation}
        return result
    with pytest.raises(ClaimV2GateRejected, match=code):
        boundary.validate_wallet_signed_claim(path, closure(), capture(),
            "signed", WALLET, current=NOW, decoder=changed)
    assert read_gate(path)["status"] == "ARMED"


def test_capture_and_wallet_identity_mismatch_fail_before_binding(tmp_path):
    path = armed(tmp_path)
    changed = capture()
    changed["transaction_sha256"] = "f" * 64
    with pytest.raises(ClaimV2GateRejected,
                       match="CLAIM_GATE_CAPTURE_BINDING_MISMATCH"):
        boundary.validate_wallet_signed_claim(path, closure(), changed,
            "signed", WALLET, current=NOW, decoder=parser)
    with pytest.raises(ClaimV2GateRejected,
                       match="WALLET_SIGNER_IDENTITY_MISMATCH"):
        boundary.validate_wallet_signed_claim(path, closure(), capture(),
            "signed", "other", current=NOW, decoder=parser)


def test_wallet_boundary_has_no_submission_or_secret_key_api():
    public = {name for name, value in vars(boundary).items()
              if callable(value) and not name.startswith("_")}
    assert not public.intersection({"submit", "send", "execute", "claim"})
    source = inspect.getsource(boundary)
    for forbidden in ("requests", "sendTransaction", "sendRawTransaction",
                      "Keypair", "secretKey", "private_key", "seed_phrase"):
        assert forbidden not in source


def test_raw_decoder_accepts_binary_and_base64_with_identical_bytes():
    raw = b"signed-wire-transaction"
    import base64
    assert boundary._raw_transaction(raw) == raw
    assert boundary._raw_transaction(base64.b64encode(raw).decode("ascii")) == raw


def test_real_decoder_rejects_unsupported_input_type():
    with pytest.raises(ClaimV2GateRejected,
                       match="INVALID_TRANSACTION_ENCODING"):
        boundary._raw_transaction(bytearray(b"signed"))


def test_versioned_message_encoder_preserves_wire_prefix():
    framed = boundary._versioned_message_bytes(
        object(), encoder=lambda _: b"\x80version-zero-message",
    )
    assert framed == b"\x80version-zero-message"


def test_versioned_message_encoder_rejects_empty_output():
    with pytest.raises(ClaimV2GateRejected,
                       match="INVALID_VERSIONED_MESSAGE_SIZE"):
        boundary._versioned_message_bytes(object(), encoder=lambda _: b"")
