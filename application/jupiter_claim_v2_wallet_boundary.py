"""Validate wallet-signed ClaimV2 bytes and bind their digest to a gate.

The full signed transaction is never persisted or returned by this module, and
there is no transaction-submission function.
"""
from __future__ import annotations

import base64
import hashlib

from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, bind_wallet_approval, require, require_armed_claim_gate,
)

MAX_TRANSACTION_BYTES = 4096


def _raw_transaction(value):
    """Accept SDK Base64 or an operator-selected binary, with identical bounds."""
    if type(value) is bytes:
        raw = value
    else:
        require(type(value) is str and 1 <= len(value) <= 8192,
                "INVALID_TRANSACTION_ENCODING")
        try:
            raw = base64.b64decode(value, validate=True)
        except Exception:
            raise ClaimV2GateRejected("INVALID_TRANSACTION_ENCODING") from None
    require(1 <= len(raw) <= MAX_TRANSACTION_BYTES,
            "INVALID_TRANSACTION_SIZE")
    return raw


def decode_transaction(value):
    try:
        raw = _raw_transaction(value)
        from solders.signature import Signature
        from solders.transaction import VersionedTransaction
        transaction = VersionedTransaction.from_bytes(raw)
        message = bytes(transaction.message)
        required = transaction.message.header.num_required_signatures
        keys = [str(key) for key in transaction.message.account_keys]
        signatures = [bytes(signature) for signature in transaction.signatures]
        require(len(signatures) == required and required > 0,
                "INVALID_REQUIRED_SIGNATURE_SET")
        return {"raw": raw, "message": message,
            "required_signers": keys[:required], "signatures": signatures,
            "default_signature": bytes(Signature.default())}
    except ClaimV2GateRejected:
        raise
    except Exception:
        raise ClaimV2GateRejected("INVALID_VERSIONED_TRANSACTION") from None


def validate_wallet_signed_claim(path, closure, capture, signed_transaction,
                                 wallet, *, current=None, decoder=None):
    """Validate exact message/signature identity, then persist only its hash."""
    gate = require_armed_claim_gate(path, closure, current=current)
    require(type(capture) is dict and len(capture) <= 32
            and capture.get("status") == "SDK_UNSIGNED_CAPTURED"
            and capture.get("execution_ready") is False
            and capture.get("fee_receipt_verified") is False,
            "FRESH_UNSIGNED_CAPTURE_REQUIRED")
    require(capture.get("message_sha256") == gate["message_sha256"]
            and capture.get("transaction_sha256") ==
                gate["unsigned_transaction_sha256"],
            "CLAIM_GATE_CAPTURE_BINDING_MISMATCH")
    identity = capture.get("identity")
    require(type(identity) is dict and identity.get("payer") == wallet
            and identity.get("partner") == wallet
            and wallet == gate["partner"],
            "WALLET_SIGNER_IDENTITY_MISMATCH")
    parser = decoder or decode_transaction
    unsigned = parser(capture.get("transaction"))
    signed = parser(signed_transaction)
    require(hashlib.sha256(unsigned["raw"]).hexdigest() ==
            gate["unsigned_transaction_sha256"],
            "UNSIGNED_TRANSACTION_HASH_MISMATCH")
    require(hashlib.sha256(unsigned["message"]).hexdigest() ==
            gate["message_sha256"], "UNSIGNED_MESSAGE_HASH_MISMATCH")
    require(signed["message"] == unsigned["message"],
            "WALLET_SIGNED_MESSAGE_CHANGED")
    require(signed["required_signers"] == unsigned["required_signers"]
            and wallet in signed["required_signers"],
            "WALLET_SIGNER_SET_MISMATCH")
    wallet_index = signed["required_signers"].index(wallet)
    require(signed["signatures"][wallet_index] != signed["default_signature"],
            "WALLET_SIGNATURE_MISSING")
    for index, signature in enumerate(signed["signatures"]):
        if index != wallet_index:
            require(signature != signed["default_signature"],
                    "REQUIRED_SIGNATURE_MISSING")
    signed_hash = hashlib.sha256(signed["raw"]).hexdigest()
    bound = bind_wallet_approval(path, gate["gate_id"], signed_hash,
                                 current=current)
    return {
        "status": "CLAIM_V2_WALLET_APPROVAL_BOUND_REVIEW_REQUIRED",
        "gate_id": bound["gate_id"],
        "closure_id": bound["closure_id"],
        "message_sha256": bound["message_sha256"],
        "unsigned_transaction_sha256": bound["unsigned_transaction_sha256"],
        "signed_transaction_sha256": signed_hash,
        "wallet_signature_verified": True,
        "wallet_review_count": 1,
        "signed_transaction_persisted": False,
        "submission_attempt_count": 0,
        "submission_permitted": False,
        "claim_submitted": False,
        "live_claim_approved": False,
        "claim_execution_ready": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
    }
