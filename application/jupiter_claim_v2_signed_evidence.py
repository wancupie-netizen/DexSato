"""Independently hash and bind wallet-signed ClaimV2 evidence without submission."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from application.jupiter_claim_v2_artifact_workflow import MAX_SIGNED_BYTES
from application.jupiter_claim_v2_one_shot_gate import ClaimV2GateRejected, read_gate
from application.jupiter_claim_v2_wallet_boundary import validate_wallet_signed_claim

MAX_JSON_BYTES = 131_072


class ClaimV2SignedEvidenceRejected(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise ClaimV2SignedEvidenceRejected(code)


def _shortvec(raw, offset=0):
    """Decode Solana's compact-u16 signature count with canonical encoding checks."""
    value = 0
    shift = 0
    start = offset
    for _ in range(3):
        require(offset < len(raw), "TRUNCATED_SIGNATURE_COUNT")
        byte = raw[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            require(value <= 0xFFFF, "SIGNATURE_COUNT_OUT_OF_RANGE")
            encoded = []
            check = value
            while True:
                item = check & 0x7F
                check >>= 7
                encoded.append(item | (0x80 if check else 0))
                if not check:
                    break
            require(raw[start:offset] == bytes(encoded),
                    "NON_CANONICAL_SIGNATURE_COUNT")
            return value, offset
        shift += 7
    raise ClaimV2SignedEvidenceRejected("INVALID_SIGNATURE_COUNT")


def independent_transaction_hashes(signed_transaction):
    """Hash raw transaction and message using only Solana wire framing."""
    require(type(signed_transaction) is bytes
            and 0 < len(signed_transaction) <= MAX_SIGNED_BYTES,
            "INVALID_SIGNED_TRANSACTION_SIZE")
    signature_count, offset = _shortvec(signed_transaction)
    require(0 < signature_count <= 32, "INVALID_SIGNATURE_COUNT")
    message_offset = offset + signature_count * 64
    require(message_offset < len(signed_transaction), "TRUNCATED_SIGNED_TRANSACTION")
    message = signed_transaction[message_offset:]
    return {
        "signed_transaction_sha256": hashlib.sha256(signed_transaction).hexdigest(),
        "message_sha256": hashlib.sha256(message).hexdigest(),
        "signed_transaction_size": len(signed_transaction),
        "signature_count": signature_count,
        "message_offset": message_offset,
    }


def _read_json(path):
    try:
        raw = Path(path).read_bytes()
        require(0 < len(raw) <= MAX_JSON_BYTES, "INVALID_JSON_SIZE")
        value = json.loads(raw.decode("utf-8"))
        require(type(value) is dict, "INVALID_JSON_OBJECT")
        return value
    except ClaimV2SignedEvidenceRejected:
        raise
    except Exception:
        raise ClaimV2SignedEvidenceRejected("INVALID_JSON_INPUT") from None


def _write_exclusive(path, value):
    target = Path(path)
    require(not target.exists(), "EVIDENCE_OUTPUT_ALREADY_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    require(len(data) <= MAX_JSON_BYTES, "EVIDENCE_OUTPUT_TOO_LARGE")
    try:
        with target.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise ClaimV2SignedEvidenceRejected("EVIDENCE_OUTPUT_ALREADY_EXISTS") from None


def bind_no_submission_evidence(gate_path, closure, capture, signed_transaction,
                                wallet, *, environment=None, current=None,
                                decoder=None, **_ignored):
    """Bind within gate TTL without asserting live-execution slot freshness."""
    env = os.environ if environment is None else environment
    for name, code in (
        ("DEXSATO_JUPITER_FEE_ENABLED", "KEEP_PRODUCTION_FEES_DISABLED"),
        ("DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED", "KEEP_CLAIM_SUBMISSION_DISABLED"),
        ("DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED", "KEEP_LIVE_APPROVAL_DISABLED"),
    ):
        require(env.get(name, "false").strip().lower() == "false", code)
    bound = validate_wallet_signed_claim(
        gate_path, closure, capture, signed_transaction, wallet,
        current=current, decoder=decoder,
    )
    gate = read_gate(gate_path)
    require(gate.get("status") == "WALLET_APPROVAL_BOUND"
            and gate.get("approval_count") == 0
            and gate.get("submission_attempt_count") == 0
            and gate.get("live_claim_approved") is False
            and gate.get("claim_submitted") is False
            and gate.get("execution_ready") is False,
            "UNSAFE_GATE_STATE_AFTER_HASH_ONLY_BINDING")
    return bound


def capture_wallet_signed_evidence(gate_path, closure, capture,
                                   signed_transaction, wallet, output_path,
                                   *, environment=None, request_post=None,
                                   current=None, decoder=None,
                                   binder=bind_no_submission_evidence):
    """Cross-check independent hashes, bind the digest, then persist hash evidence."""
    require(not Path(output_path).exists(), "EVIDENCE_OUTPUT_ALREADY_EXISTS")
    require(type(capture) is dict and capture.get("status") == "SDK_UNSIGNED_CAPTURED",
            "FRESH_UNSIGNED_CAPTURE_REQUIRED")
    independent = independent_transaction_hashes(signed_transaction)
    require(independent["message_sha256"] == capture.get("message_sha256"),
            "INDEPENDENT_MESSAGE_HASH_MISMATCH")
    bound = binder(
        gate_path, closure, capture, signed_transaction, wallet,
        environment=environment, request_post=request_post,
        current=current, decoder=decoder,
    )
    require(bound.get("signed_transaction_sha256") ==
            independent["signed_transaction_sha256"],
            "INDEPENDENT_SIGNED_TRANSACTION_HASH_MISMATCH")
    require(bound.get("message_sha256") == independent["message_sha256"],
            "BOUND_MESSAGE_HASH_MISMATCH")
    report = {
        "status": "CLAIM_V2_WALLET_SIGNED_HASH_INDEPENDENTLY_VERIFIED",
        "gate_id": bound["gate_id"],
        "closure_id": bound["closure_id"],
        **independent,
        "capture_message_sha256": capture["message_sha256"],
        "independent_hash_verified": True,
        "wallet_signature_verified": True,
        "signed_transaction_persisted": False,
        "rpc_freshness_verified": False,
        "capture_freshness_policy": "GATE_TTL_ONLY_NO_SUBMISSION",
        "live_reconstruction_required": True,
        "gate_status": "WALLET_APPROVAL_BOUND",
        "live_claim_approved": False,
        "approval_count": 0,
        "submission_attempt_count": 0,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
    }
    _write_exclusive(output_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--closure", required=True)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--signed-transaction-file", required=True)
    parser.add_argument("--wallet", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        signed = Path(args.signed_transaction_file).read_bytes()
        report = capture_wallet_signed_evidence(
            args.gate, _read_json(args.closure), _read_json(args.capture),
            signed, args.wallet, args.output,
        )
        print(json.dumps(report, separators=(",", ":")))
        return 2
    except Exception as error:
        reason = (str(error) if isinstance(
                    error, (ClaimV2SignedEvidenceRejected, ClaimV2GateRejected))
                  else "SIGNED_EVIDENCE_INPUT_OR_VERIFICATION_UNAVAILABLE")
        print(json.dumps({
            "status": "CLAIM_V2_WALLET_SIGNED_EVIDENCE_NOT_VERIFIED",
            "reason": reason,
            "execution_ready": False,
            "fee_receipt_verified": False,
        }, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
