"""Persistent one-shot ClaimV2 wallet-approval gate; no submission support."""
from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from application.jupiter_claim_v2_gate_design import (
    CONFIRMATION_PHRASE, GATE_TTL_SECONDS, design_one_shot_claim_gate,
)
from application.jupiter_claim_v2_simulation_closure import read_json as read_closure

MAX_GATE_BYTES = 32_768
FEATURE_FLAG = "DEXSATO_JUPITER_CLAIM_GATE_ENABLED"


class ClaimV2GateRejected(RuntimeError):
    """Fixed public rejection code; supplied data is never echoed."""


def require(condition, code):
    if not condition:
        raise ClaimV2GateRejected(code)


def utc_now():
    return datetime.now(timezone.utc)


def _stamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "INVALID_CLAIM_GATE_TIMESTAMP")
        return parsed.astimezone(timezone.utc)
    except ClaimV2GateRejected:
        raise
    except Exception:
        raise ClaimV2GateRejected("INVALID_CLAIM_GATE_TIMESTAMP") from None


def read_gate(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= MAX_GATE_BYTES, "CLAIM_GATE_FILE_TOO_LARGE")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_CLAIM_GATE_KEY")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except ClaimV2GateRejected:
        raise
    except Exception:
        raise ClaimV2GateRejected("INVALID_CLAIM_GATE_FILE") from None
    require(type(value) is dict and len(value) <= 64, "INVALID_CLAIM_GATE_FILE")
    return value


def write_gate(path, value, *, exclusive=False):
    path = Path(path)
    require(path.name and path.suffix.lower() == ".json", "INVALID_CLAIM_GATE_PATH")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return
    temporary = path.with_name(path.name + ".tmp")
    require(not temporary.exists(), "CLAIM_GATE_TEMPORARY_FILE_EXISTS")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def arm_claim_gate(path, closure, confirmation, *, environment=None, current=None):
    """Create an expiring gate record; never authorize submission."""
    env = os.environ if environment is None else environment
    require(env.get(FEATURE_FLAG, "false").strip().lower() == "true",
            "CLAIM_GATE_FEATURE_DISABLED")
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower() == "false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    require(confirmation == CONFIRMATION_PHRASE,
            "EXPLICIT_CLAIM_CONFIRMATION_REQUIRED")
    design = design_one_shot_claim_gate(closure)
    current = current or utc_now()
    require(current.tzinfo is not None, "INVALID_CLAIM_GATE_TIMESTAMP")
    gate = {
        "version": 1,
        "gate_id": secrets.token_hex(16),
        "status": "ARMED",
        "closure_id": design["closure_id"],
        "message_sha256": design["message_sha256"],
        "unsigned_transaction_sha256": design["transaction_sha256"],
        "mint": design["mint"],
        "referral_account": design["referral_account"],
        "partner": design["partner"],
        "exact_claim_raw": design["exact_claim_raw"],
        "maximum_claim_raw": design["maximum_claim_raw"],
        "expected_partner_raw": design["expected_partner_raw"],
        "expected_project_raw": design["expected_project_raw"],
        "armed_at": current.astimezone(timezone.utc).isoformat(),
        "expires_at": (current.astimezone(timezone.utc)
                       + timedelta(seconds=GATE_TTL_SECONDS)).isoformat(),
        "wallet_review_count": 0,
        "submission_attempt_count": 0,
        "signed_transaction_sha256": None,
        "wallet_signature_verified": False,
        "submission_permitted": False,
        "claim_submitted": False,
        "live_claim_approved": False,
        "claim_execution_ready": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
    }
    write_gate(path, gate, exclusive=True)
    return gate


def require_armed_claim_gate(path, closure, *, current=None):
    gate = read_gate(path)
    design = design_one_shot_claim_gate(closure)
    current = current or utc_now()
    require(gate.get("status") == "ARMED", "CLAIM_GATE_NOT_ARMED")
    require(current <= _stamp(gate.get("expires_at", "")), "CLAIM_GATE_EXPIRED")
    expected = {
        "closure_id": design["closure_id"],
        "message_sha256": design["message_sha256"],
        "unsigned_transaction_sha256": design["transaction_sha256"],
        "mint": design["mint"],
        "referral_account": design["referral_account"],
        "partner": design["partner"],
        "exact_claim_raw": "5000",
        "maximum_claim_raw": "5000",
        "expected_partner_raw": "4000",
        "expected_project_raw": "1000",
    }
    require(all(gate.get(key) == value for key, value in expected.items()),
            "CLAIM_GATE_CLOSURE_BINDING_MISMATCH")
    require(gate.get("wallet_review_count") == 0
            and gate.get("submission_attempt_count") == 0
            and gate.get("signed_transaction_sha256") is None
            and gate.get("submission_permitted") is False
            and gate.get("claim_submitted") is False
            and gate.get("live_claim_approved") is False
            and gate.get("claim_execution_ready") is False
            and gate.get("execution_ready") is False,
            "UNSAFE_OR_USED_CLAIM_GATE")
    return gate


def bind_wallet_approval(path, gate_id, signed_transaction_sha256, *, current=None):
    """Bind one wallet-reviewed digest; still never permit submission."""
    gate = read_gate(path)
    current = current or utc_now()
    require(gate.get("gate_id") == gate_id, "CLAIM_GATE_ID_MISMATCH")
    require(current <= _stamp(gate.get("expires_at", "")), "CLAIM_GATE_EXPIRED")
    require(type(signed_transaction_sha256) is str
            and len(signed_transaction_sha256) == 64
            and all(char in "0123456789abcdef"
                    for char in signed_transaction_sha256),
            "INVALID_SIGNED_TRANSACTION_HASH")
    if gate.get("status") == "WALLET_APPROVAL_BOUND":
        require(gate.get("signed_transaction_sha256") == signed_transaction_sha256,
                "CLAIM_GATE_REPLAY_MISMATCH")
        return gate
    require(gate.get("status") == "ARMED"
            and gate.get("wallet_review_count") == 0,
            "CLAIM_GATE_NOT_ARMED")
    gate.update(status="WALLET_APPROVAL_BOUND",
        signed_transaction_sha256=signed_transaction_sha256,
        wallet_review_count=1, wallet_approved_at=current.isoformat(),
        wallet_signature_verified=True, submission_permitted=False,
        claim_submitted=False, live_claim_approved=False,
        claim_execution_ready=False, execution_ready=False,
        fee_receipt_verified=False)
    write_gate(path, gate)
    return gate


def reserve_submission(path, gate_id, signed_transaction_sha256, *, current=None):
    """Consume the single submission attempt before any provider call."""
    gate = read_gate(path)
    current = current or utc_now()
    require(gate.get("status") == "WALLET_APPROVAL_BOUND",
            "CLAIM_WALLET_APPROVAL_REQUIRED")
    require(gate.get("gate_id") == gate_id, "CLAIM_GATE_ID_MISMATCH")
    require(current <= _stamp(gate.get("expires_at", "")), "CLAIM_GATE_EXPIRED")
    require(gate.get("signed_transaction_sha256") == signed_transaction_sha256,
            "CLAIM_GATE_SIGNED_TRANSACTION_MISMATCH")
    require(gate.get("wallet_signature_verified") is True
            and gate.get("wallet_review_count") == 1
            and gate.get("submission_attempt_count") == 0
            and gate.get("claim_submitted") is False,
            "CLAIM_GATE_ALREADY_USED")
    require(gate.get("submission_permitted") is True
            and gate.get("live_claim_approved") is True,
            "LIVE_CLAIM_APPROVAL_REQUIRED")
    gate.update(status="SUBMISSION_PENDING", submission_attempt_count=1,
        submission_reserved_at=current.isoformat(), submission_permitted=False,
        claim_submitted=False,
        claim_execution_ready=False, execution_ready=False)
    write_gate(path, gate)
    return gate


def record_submission_result(path, gate_id, *, signature=None, failure_reason=None):
    gate = read_gate(path)
    require(gate.get("status") == "SUBMISSION_PENDING"
            and gate.get("gate_id") == gate_id
            and gate.get("submission_attempt_count") == 1,
            "CLAIM_SUBMISSION_NOT_PENDING")
    if signature is not None:
        require(type(signature) is str and 64 <= len(signature) <= 96,
                "INVALID_CLAIM_SIGNATURE")
        gate.update(status="FINALIZATION_PENDING", signature=signature,
            claim_submitted=True, provider_status="Success")
    else:
        require(failure_reason in {"RPC_UNAVAILABLE", "RPC_HTTP_ERROR",
            "RPC_REJECTED", "INVALID_RPC_RESPONSE"}, "INVALID_FAILURE_REASON")
        gate.update(status="FAILED", provider_status="Failed",
            failure_reason=failure_reason, claim_submitted=False)
    gate.update(submission_permitted=False, live_claim_approved=False,
        claim_execution_ready=False, execution_ready=False,
        fee_receipt_verified=False)
    write_gate(path, gate)
    return gate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)
    try:
        closure = read_closure(args.closure)
        gate = arm_claim_gate(args.output, closure, args.confirm)
        print(json.dumps({key: gate[key] for key in
            ("status", "gate_id", "expires_at", "submission_permitted",
             "execution_ready")}))
        return 0
    except ClaimV2GateRejected as error:
        reason = str(error)
    except Exception:
        reason = "CLAIM_GATE_INPUT_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status": "CLAIM_GATE_NOT_ARMED", "reason": reason,
        "submission_permitted": False, "execution_ready": False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
