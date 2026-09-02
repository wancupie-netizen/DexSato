"""Explicit, persistent ClaimV2 live-approval transition; never submits."""
from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import timedelta

from application.jupiter_claim_v2_one_shot_gate import (
    ClaimV2GateRejected, _stamp, read_gate, require, utc_now, write_gate,
)

FEATURE_FLAG = "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED"
SUBMISSION_FLAG = "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED"
CONFIRMATION = "I APPROVE ONE LIVE CLAIM V2"
APPROVAL_TTL_SECONDS = 90


def approve_live_claim(path, gate_id, signed_transaction_sha256, confirmation,
                       *, environment=None, current=None):
    """Approve one exact bound digest without signing or submitting it."""
    env = os.environ if environment is None else environment
    require(env.get(FEATURE_FLAG, "false").strip().lower() == "true",
            "CLAIM_LIVE_APPROVAL_FEATURE_DISABLED")
    require(env.get(SUBMISSION_FLAG, "false").strip().lower() == "false",
            "DISABLE_SUBMISSION_DURING_APPROVAL")
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED", "false").strip().lower() == "false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    require(confirmation == CONFIRMATION, "EXPLICIT_LIVE_CLAIM_CONFIRMATION_REQUIRED")
    gate = read_gate(path)
    current = current or utc_now()
    require(current.tzinfo is not None, "INVALID_CLAIM_GATE_TIMESTAMP")
    require(gate.get("status") == "WALLET_APPROVAL_BOUND",
            "CLAIM_WALLET_APPROVAL_REQUIRED")
    require(gate.get("gate_id") == gate_id, "CLAIM_GATE_ID_MISMATCH")
    require(current <= _stamp(gate.get("expires_at", "")), "CLAIM_GATE_EXPIRED")
    require(type(signed_transaction_sha256) is str
            and signed_transaction_sha256 == gate.get("signed_transaction_sha256"),
            "CLAIM_GATE_SIGNED_TRANSACTION_MISMATCH")
    require(gate.get("wallet_signature_verified") is True
            and gate.get("wallet_review_count") == 1
            and gate.get("submission_attempt_count") == 0
            and gate.get("claim_submitted") is False
            and gate.get("approval_count", 0) == 0,
            "CLAIM_GATE_ALREADY_USED_OR_APPROVED")
    approval_expires = min(
        _stamp(gate["expires_at"]), current + timedelta(seconds=APPROVAL_TTL_SECONDS)
    )
    gate.update(
        status="LIVE_CLAIM_APPROVED",
        approval_id=secrets.token_hex(16),
        approval_count=1,
        approved_signed_transaction_sha256=signed_transaction_sha256,
        live_claim_approved_at=current.isoformat(),
        approval_expires_at=approval_expires.isoformat(),
        submission_permitted=True,
        live_claim_approved=True,
        claim_execution_ready=False,
        execution_ready=False,
        fee_receipt_verified=False,
    )
    write_gate(path, gate)
    return {
        "status": "CLAIM_V2_LIVE_APPROVAL_BOUND",
        "gate_id": gate["gate_id"],
        "approval_id": gate["approval_id"],
        "approval_expires_at": gate["approval_expires_at"],
        "submission_permitted": True,
        "claim_submitted": False,
        "execution_ready": False,
    }


def audit_gate_consumption(path):
    gate = read_gate(path)
    require(gate.get("approval_count") == 1, "CLAIM_LIVE_APPROVAL_NOT_RECORDED")
    require(gate.get("wallet_review_count") == 1, "INVALID_WALLET_REVIEW_COUNT")
    require(gate.get("submission_attempt_count") in (0, 1),
            "INVALID_SUBMISSION_ATTEMPT_COUNT")
    status = gate.get("status")
    if gate.get("submission_attempt_count") == 0:
        require(status == "LIVE_CLAIM_APPROVED"
                and gate.get("submission_permitted") is True
                and gate.get("claim_submitted") is False,
                "INVALID_UNCONSUMED_APPROVAL_STATE")
        consumed = False
    else:
        require(status in ("SUBMISSION_PENDING", "FINALIZATION_PENDING", "FAILED",
                           "FINALIZED_VERIFIED")
                and gate.get("submission_permitted") is False,
                "INVALID_CONSUMED_APPROVAL_STATE")
        consumed = True
    return {"status": "CLAIM_V2_GATE_CONSUMPTION_AUDIT_REVIEW_REQUIRED",
        "gate_id": gate.get("gate_id"), "approval_count": 1,
        "submission_attempt_count": gate.get("submission_attempt_count"),
        "approval_consumed": consumed, "claim_submitted": gate.get("claim_submitted"),
        "execution_ready": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--signed-transaction-sha256", required=True)
    parser.add_argument("--confirm", required=True)
    args = parser.parse_args(argv)
    try:
        report = approve_live_claim(args.gate, args.gate_id,
            args.signed_transaction_sha256, args.confirm)
        print(json.dumps(report)); return 2
    except ClaimV2GateRejected as error:
        reason = str(error)
    except Exception:
        reason = "CLAIM_LIVE_APPROVAL_INPUT_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status":"CLAIM_V2_LIVE_APPROVAL_NOT_BOUND",
        "reason":reason,"submission_permitted":False,"execution_ready":False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
