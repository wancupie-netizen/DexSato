"""Close hash-only ClaimV2 evidence and design a fresh reconstruction boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from application.jupiter_claim_v2_one_shot_gate import read_gate

MAX_JSON_BYTES = 131_072
FALSE_FLAGS = (
    "DEXSATO_JUPITER_FEE_ENABLED",
    "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED",
    "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED",
)


class ClaimV2EvidenceClosureRejected(RuntimeError):
    """A fixed public rejection code; supplied values are never echoed."""


def require(condition, code):
    if not condition:
        raise ClaimV2EvidenceClosureRejected(code)


def _safe_environment(environment):
    env = os.environ if environment is None else environment
    require(all(env.get(name, "false").strip().lower() == "false"
                for name in FALSE_FLAGS), "KEEP_CLAIM_EXECUTION_DISABLED")
    return env


def _read_json(path):
    try:
        raw = Path(path).read_bytes()
        require(0 < len(raw) <= MAX_JSON_BYTES, "INVALID_JSON_SIZE")
        value = json.loads(raw.decode("utf-8-sig"))
        require(type(value) is dict and len(value) <= 64, "INVALID_JSON_OBJECT")
        return value
    except ClaimV2EvidenceClosureRejected:
        raise
    except Exception:
        raise ClaimV2EvidenceClosureRejected("INVALID_JSON_INPUT") from None


def _write_exclusive(path, value):
    target = Path(path)
    require(not target.exists(), "OUTPUT_ALREADY_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    require(len(encoded) <= MAX_JSON_BYTES, "OUTPUT_TOO_LARGE")
    try:
        with target.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise ClaimV2EvidenceClosureRejected("OUTPUT_ALREADY_EXISTS") from None


def _hex64(value):
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _closure_id(core):
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def close_signed_evidence(gate, evidence, *, environment=None, current=None):
    """Create an immutable audit closure without changing or consuming the gate."""
    _safe_environment(environment)
    require(type(gate) is dict and gate.get("status") == "WALLET_APPROVAL_BOUND",
            "WALLET_BOUND_GATE_REQUIRED")
    require(type(evidence) is dict and evidence.get("status") ==
            "CLAIM_V2_WALLET_SIGNED_HASH_INDEPENDENTLY_VERIFIED",
            "VERIFIED_SIGNED_EVIDENCE_REQUIRED")
    require(gate.get("gate_id") == evidence.get("gate_id")
            and gate.get("closure_id") == evidence.get("closure_id"),
            "GATE_EVIDENCE_IDENTITY_MISMATCH")
    require(_hex64(evidence.get("message_sha256"))
            and evidence.get("message_sha256") == gate.get("message_sha256")
            and evidence.get("capture_message_sha256") == gate.get("message_sha256"),
            "GATE_EVIDENCE_MESSAGE_MISMATCH")
    require(_hex64(evidence.get("signed_transaction_sha256"))
            and evidence.get("signed_transaction_sha256") ==
                gate.get("signed_transaction_sha256"),
            "GATE_EVIDENCE_SIGNED_HASH_MISMATCH")
    require(evidence.get("independent_hash_verified") is True
            and evidence.get("wallet_signature_verified") is True
            and evidence.get("signed_transaction_persisted") is False
            and evidence.get("rpc_freshness_verified") is False
            and evidence.get("live_reconstruction_required") is True,
            "SIGNED_EVIDENCE_POLICY_MISMATCH")
    require(gate.get("wallet_review_count") == 1
            and gate.get("approval_count") == 0
            and gate.get("submission_attempt_count") == 0
            and gate.get("submission_permitted") is False
            and gate.get("live_claim_approved") is False
            and gate.get("claim_submitted") is False
            and gate.get("execution_ready") is False,
            "UNSAFE_OR_USED_SOURCE_GATE")
    require(gate.get("exact_claim_raw") == "5000"
            and gate.get("maximum_claim_raw") == "5000"
            and gate.get("expected_partner_raw") == "4000"
            and gate.get("expected_project_raw") == "1000",
            "CLAIM_AMOUNT_CONTRACT_MISMATCH")
    core = {
        "source_gate_id": gate["gate_id"],
        "simulation_closure_id": gate["closure_id"],
        "message_sha256": gate["message_sha256"],
        "signed_transaction_sha256": gate["signed_transaction_sha256"],
        "mint": gate["mint"],
        "referral_account": gate["referral_account"],
        "partner": gate["partner"],
        "exact_claim_raw": "5000",
        "expected_partner_raw": "4000",
        "expected_project_raw": "1000",
    }
    now = current or datetime.now(timezone.utc)
    require(now.tzinfo is not None, "INVALID_CLOSURE_TIMESTAMP")
    return {
        "status": "CLAIM_V2_SIGNED_EVIDENCE_CLOSED",
        "evidence_closure_id": _closure_id(core),
        **core,
        "closed_at": now.astimezone(timezone.utc).isoformat(),
        "source_gate_status": "WALLET_APPROVAL_BOUND",
        "source_gate_reusable": False,
        "prior_signed_transaction_reusable": False,
        "signed_transaction_persisted": False,
        "rpc_freshness_verified": False,
        "live_reconstruction_required": True,
        "live_claim_approved": False,
        "submission_permitted": False,
        "submission_attempt_count": 0,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
    }


def design_fresh_reconstruction(closure, *, environment=None):
    """Describe the next boundary; never constructs or returns transaction bytes."""
    _safe_environment(environment)
    require(type(closure) is dict and closure.get("status") ==
            "CLAIM_V2_SIGNED_EVIDENCE_CLOSED",
            "SIGNED_EVIDENCE_CLOSURE_REQUIRED")
    require(_hex64(closure.get("evidence_closure_id"))
            and closure.get("source_gate_reusable") is False
            and closure.get("prior_signed_transaction_reusable") is False
            and closure.get("live_reconstruction_required") is True,
            "INVALID_SIGNED_EVIDENCE_CLOSURE")
    require(closure.get("live_claim_approved") is False
            and closure.get("submission_permitted") is False
            and closure.get("submission_attempt_count") == 0
            and closure.get("claim_submitted") is False
            and closure.get("execution_ready") is False,
            "UNSAFE_SIGNED_EVIDENCE_CLOSURE")
    return {
        "status": "CLAIM_V2_FRESH_RECONSTRUCTION_BOUNDARY_REVIEW_REQUIRED",
        "evidence_closure_id": closure["evidence_closure_id"],
        "retired_source_gate_id": closure["source_gate_id"],
        "exact_claim_raw": closure["exact_claim_raw"],
        "expected_partner_raw": closure["expected_partner_raw"],
        "expected_project_raw": closure["expected_project_raw"],
        "fresh_rpc_mainnet_verification_required": True,
        "fresh_funded_balance_verification_required": True,
        "fresh_blockhash_required": True,
        "fresh_unsigned_capture_required": True,
        "fresh_simulation_closure_required": True,
        "fresh_gate_required": True,
        "fresh_wallet_signature_required": True,
        "prior_message_reusable": False,
        "prior_signed_transaction_reusable": False,
        "transaction_constructed": False,
        "transaction_signed": False,
        "live_claim_approved": False,
        "submission_permitted": False,
        "submission_attempt_count": 0,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    close = commands.add_parser("close")
    close.add_argument("--gate", required=True)
    close.add_argument("--evidence", required=True)
    close.add_argument("--output", required=True)
    design = commands.add_parser("design")
    design.add_argument("--closure", required=True)
    design.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "close":
            report = close_signed_evidence(
                read_gate(args.gate), _read_json(args.evidence))
        else:
            report = design_fresh_reconstruction(_read_json(args.closure))
        _write_exclusive(args.output, report)
        print(json.dumps(report, separators=(",", ":")))
        return 2
    except ClaimV2EvidenceClosureRejected as error:
        reason = str(error)
    except Exception:
        reason = "EVIDENCE_CLOSURE_INPUT_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({
        "status": "CLAIM_V2_EVIDENCE_CLOSURE_NOT_VERIFIED",
        "reason": reason,
        "live_claim_approved": False,
        "submission_permitted": False,
        "transaction_submitted": False,
        "execution_ready": False,
    }, separators=(",", ":")))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
