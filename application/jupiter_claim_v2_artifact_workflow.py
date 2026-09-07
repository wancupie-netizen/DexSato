"""Fresh ClaimV2 artifact generation and wallet-evidence binding without submission."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from application.jupiter_claim_v2_auxiliary import audit_auxiliary_instructions
from application.jupiter_claim_v2_fresh_approval import inspect_fresh_capture
from application.jupiter_claim_v2_one_shot_gate import (
    CONFIRMATION_PHRASE,
    arm_claim_gate,
    read_gate,
)
from application.jupiter_claim_v2_sdk_capture import run_sdk
from application.jupiter_claim_v2_simulation import audit_claim_simulation
from application.jupiter_claim_v2_simulation_closure import close_funded_simulation
from application.jupiter_claim_v2_wallet_boundary import validate_wallet_signed_claim

MAX_JSON_BYTES = 131_072
MAX_SIGNED_BYTES = 16_384
ARTIFACT_NAMES = {
    "capture": "unsigned_claim_v2_capture.json",
    "binding": "claim_v2_compiled_binding_report.json",
    "auxiliary": "claim_v2_auxiliary_report.json",
    "simulation": "claim_v2_simulation_report.json",
    "closure": "claim_v2_simulation_closure.json",
}


class ClaimV2ArtifactWorkflowRejected(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise ClaimV2ArtifactWorkflowRejected(code)


def _flag(env, name):
    return env.get(name, "false").strip().lower()


def _safe_environment(env, *, generation=False):
    require(_flag(env, "DEXSATO_JUPITER_FEE_ENABLED") == "false",
            "KEEP_PRODUCTION_FEES_DISABLED")
    require(_flag(env, "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED") == "false",
            "KEEP_CLAIM_SUBMISSION_DISABLED")
    require(_flag(env, "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED") == "false",
            "KEEP_LIVE_APPROVAL_DISABLED")
    if generation:
        require(_flag(env, "DEXSATO_JUPITER_CLAIM_GATE_ENABLED") == "true",
                "CLAIM_GATE_FEATURE_REQUIRED")


def _read_json(path, maximum=MAX_JSON_BYTES):
    try:
        raw = Path(path).read_bytes()
        require(0 < len(raw) <= maximum, "INVALID_JSON_SIZE")
        value = json.loads(raw.decode("utf-8"))
        require(type(value) is dict, "INVALID_JSON_OBJECT")
        return value
    except ClaimV2ArtifactWorkflowRejected:
        raise
    except Exception:
        raise ClaimV2ArtifactWorkflowRejected("INVALID_JSON_INPUT") from None


def _write_json(path, value, *, exclusive=True):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")
    require(len(data) <= MAX_JSON_BYTES, "ARTIFACT_TOO_LARGE")
    mode = "xb" if exclusive else "wb"
    try:
        with target.open(mode) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise ClaimV2ArtifactWorkflowRejected("OUTPUT_ALREADY_EXISTS") from None


def generate_fresh_artifacts(identity, output_dir, gate_path, confirmation,
                             *, environment=None, sdk_runner=run_sdk,
                             auxiliary_runner=audit_auxiliary_instructions,
                             simulation_runner=audit_claim_simulation,
                             closure_runner=close_funded_simulation,
                             gate_runner=arm_claim_gate, request_post=None):
    """Generate a fresh read-only evidence set and arm an unapproved gate."""
    env = os.environ if environment is None else environment
    _safe_environment(env, generation=True)
    output = Path(output_dir)
    gate_file = Path(gate_path)
    require(not output.exists(), "OUTPUT_DIRECTORY_ALREADY_EXISTS")
    require(not gate_file.exists(), "GATE_ALREADY_EXISTS")
    require(type(identity) is dict, "INVALID_IDENTITY")

    capture, binding = sdk_runner(identity, environment=env)
    auxiliary = auxiliary_runner(capture, binding)
    simulation = simulation_runner(
        capture, binding, auxiliary, environment=env, request_post=request_post,
    )
    closure = closure_runner(capture, binding, auxiliary, simulation)

    output.mkdir(parents=True, exist_ok=False)
    reports = {"capture": capture, "binding": binding, "auxiliary": auxiliary,
               "simulation": simulation, "closure": closure}
    for role, report in reports.items():
        _write_json(output / ARTIFACT_NAMES[role], report)
    gate = gate_runner(gate_file, closure, confirmation, environment=env)
    return {
        "status": "FRESH_CLAIM_V2_ARTIFACTS_REVIEW_REQUIRED",
        "closure_id": closure["closure_id"],
        "gate_id": gate["gate_id"],
        "artifact_count": len(reports),
        "wallet_signature_verified": False,
        "live_claim_approved": False,
        "submission_attempt_count": 0,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
    }


def bind_wallet_signed_evidence(gate_path, closure, capture, signed_transaction,
                                wallet, *, environment=None, request_post=None,
                                current=None, decoder=None):
    """Verify wallet-signed bytes, persist only their digest, and never approve."""
    env = os.environ if environment is None else environment
    _safe_environment(env)
    require(type(signed_transaction) is bytes
            and 0 < len(signed_transaction) <= MAX_SIGNED_BYTES,
            "INVALID_SIGNED_TRANSACTION_SIZE")
    freshness = inspect_fresh_capture(
        gate_path, closure, capture, environment=env, post=request_post,
    )
    bound = validate_wallet_signed_claim(
        gate_path, closure, capture, signed_transaction, wallet,
        current=current, decoder=decoder,
    )
    gate = read_gate(gate_path)
    require(gate.get("status") == "WALLET_APPROVAL_BOUND"
            and gate.get("approval_count") == 0
            and gate.get("submission_attempt_count") == 0
            and gate.get("live_claim_approved") is False,
            "UNSAFE_GATE_STATE_AFTER_WALLET_BINDING")
    return {
        "status": "CLAIM_V2_WALLET_SIGNED_EVIDENCE_CAPTURED_NO_SUBMISSION",
        "gate_id": bound["gate_id"],
        "closure_id": bound["closure_id"],
        "message_sha256": bound["message_sha256"],
        "signed_transaction_sha256": bound["signed_transaction_sha256"],
        "capture_slot": freshness["capture_slot"],
        "slot_age": freshness["slot_age"],
        "wallet_signature_verified": True,
        "signed_transaction_persisted": False,
        "live_claim_approved": False,
        "approval_count": 0,
        "submission_attempt_count": 0,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--identity", required=True)
    generate.add_argument("--output-dir", required=True)
    generate.add_argument("--gate", required=True)
    generate.add_argument("--confirm", required=True)
    bind = commands.add_parser("bind")
    bind.add_argument("--gate", required=True)
    bind.add_argument("--closure", required=True)
    bind.add_argument("--capture", required=True)
    bind.add_argument("--signed-transaction-file", required=True)
    bind.add_argument("--wallet", required=True)
    bind.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            report = generate_fresh_artifacts(
                _read_json(args.identity), args.output_dir, args.gate, args.confirm,
            )
        else:
            signed = Path(args.signed_transaction_file).read_bytes()
            report = bind_wallet_signed_evidence(
                args.gate, _read_json(args.closure), _read_json(args.capture),
                signed, args.wallet,
            )
            _write_json(args.output, report)
        print(json.dumps(report, separators=(",", ":")))
        return 2
    except Exception as error:
        reason = str(error) if isinstance(error, ClaimV2ArtifactWorkflowRejected) else "WORKFLOW_INPUT_OR_UPSTREAM_UNAVAILABLE"
        print(json.dumps({"status": "CLAIM_V2_ARTIFACT_WORKFLOW_NOT_VERIFIED",
                          "reason": reason, "execution_ready": False,
                          "fee_receipt_verified": False}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
