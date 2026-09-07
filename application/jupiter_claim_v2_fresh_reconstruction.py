"""Plan and prepare fresh ClaimV2 artifacts without signing or live approval."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from application.jupiter_claim_v2_artifact_workflow import (
    ARTIFACT_NAMES, generate_fresh_artifacts,
)
from application.jupiter_claim_v2_evidence_closure import (
    design_fresh_reconstruction,
)
from application.jupiter_claim_v2_one_shot_gate import read_gate

MAX_JSON_BYTES = 131_072
FALSE_FLAGS = (
    "DEXSATO_JUPITER_FEE_ENABLED",
    "DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED",
    "DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED",
)


class ClaimV2FreshReconstructionRejected(RuntimeError):
    """Fixed public rejection code; supplied values are never echoed."""


def require(condition, code):
    if not condition:
        raise ClaimV2FreshReconstructionRejected(code)


def _safe_environment(environment, *, generation=False):
    env = os.environ if environment is None else environment
    require(all(env.get(name, "false").strip().lower() == "false"
                for name in FALSE_FLAGS), "KEEP_CLAIM_EXECUTION_DISABLED")
    if generation:
        require(env.get("DEXSATO_JUPITER_CLAIM_GATE_ENABLED", "false")
                .strip().lower() == "true", "CLAIM_GATE_FEATURE_REQUIRED")
    return env


def _read_json(path):
    try:
        raw = Path(path).read_bytes()
        require(0 < len(raw) <= MAX_JSON_BYTES, "INVALID_JSON_SIZE")
        value = json.loads(raw.decode("utf-8-sig"))
        require(type(value) is dict and len(value) <= 96, "INVALID_JSON_OBJECT")
        return value
    except ClaimV2FreshReconstructionRejected:
        raise
    except Exception:
        raise ClaimV2FreshReconstructionRejected("INVALID_JSON_INPUT") from None


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
        raise ClaimV2FreshReconstructionRejected("OUTPUT_ALREADY_EXISTS") from None


def _copy_exclusive(source, destination):
    source, destination = Path(source), Path(destination)
    require(source.is_file() and not destination.exists(),
            "GATE_REVIEW_COPY_PRECONDITION_FAILED")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with source.open("rb") as incoming, destination.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
            outgoing.flush()
            os.fsync(outgoing.fileno())
    except FileExistsError:
        raise ClaimV2FreshReconstructionRejected(
            "GATE_REVIEW_ALREADY_EXISTS") from None
    require(source.read_bytes() == destination.read_bytes(),
            "GATE_REVIEW_COPY_MISMATCH")


def _hex64(value):
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def verify_reconstruction_plan(evidence_closure, boundary, *, environment=None):
    """Bind the operator plan to the exact F.6C.5 closure without side effects."""
    _safe_environment(environment)
    require(type(evidence_closure) is dict and type(boundary) is dict,
            "INVALID_RECONSTRUCTION_INPUT")
    expected = design_fresh_reconstruction(
        evidence_closure, environment=environment)
    require(boundary == expected, "RECONSTRUCTION_BOUNDARY_MISMATCH")
    require(boundary.get("fresh_rpc_mainnet_verification_required") is True
            and boundary.get("fresh_funded_balance_verification_required") is True
            and boundary.get("fresh_blockhash_required") is True
            and boundary.get("fresh_unsigned_capture_required") is True
            and boundary.get("fresh_simulation_closure_required") is True
            and boundary.get("fresh_gate_required") is True
            and boundary.get("fresh_wallet_signature_required") is True,
            "INCOMPLETE_FRESH_RECONSTRUCTION_REQUIREMENTS")
    return {
        "status": "CLAIM_V2_FRESH_RECONSTRUCTION_PLAN_VERIFIED",
        "evidence_closure_id": evidence_closure["evidence_closure_id"],
        "retired_source_gate_id": evidence_closure["source_gate_id"],
        "prior_message_sha256": evidence_closure["message_sha256"],
        "prior_signed_transaction_sha256":
            evidence_closure["signed_transaction_sha256"],
        "prior_gate_reusable": False,
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
    }


def prepare_fresh_reconstruction(identity, evidence_closure, boundary,
                                 output_dir, gate_path, confirmation,
                                 *, environment=None,
                                 generator=generate_fresh_artifacts,
                                 json_reader=_read_json,
                                 gate_reader=read_gate,
                                 gate_review_writer=_copy_exclusive):
    """Generate fresh unsigned artifacts and an unapproved gate review copy."""
    env = _safe_environment(environment, generation=True)
    plan = verify_reconstruction_plan(
        evidence_closure, boundary, environment=env)
    output, gate_file = Path(output_dir), Path(gate_path)
    review_path = output / "claim_v2_gate_review.json"
    require(not output.exists() and not gate_file.exists(),
            "FRESH_OUTPUT_OR_GATE_ALREADY_EXISTS")
    generated = generator(identity, output, gate_file, confirmation,
                          environment=env)
    require(type(generated) is dict and generated.get("status") ==
            "FRESH_CLAIM_V2_ARTIFACTS_REVIEW_REQUIRED"
            and generated.get("artifact_count") == 5
            and generated.get("wallet_signature_verified") is False
            and generated.get("live_claim_approved") is False
            and generated.get("submission_attempt_count") == 0
            and generated.get("transaction_submitted") is False
            and generated.get("claim_submitted") is False
            and generated.get("execution_ready") is False,
            "FRESH_ARTIFACT_GENERATION_CONTRACT_MISMATCH")
    capture = json_reader(output / ARTIFACT_NAMES["capture"])
    simulation_closure = json_reader(output / ARTIFACT_NAMES["closure"])
    gate = gate_reader(gate_file)
    require(capture.get("status") == "SDK_UNSIGNED_CAPTURED"
            and _hex64(capture.get("message_sha256"))
            and _hex64(capture.get("transaction_sha256"))
            and type(capture.get("rpc_slot")) is int
            and capture.get("rpc_slot") > 0
            and capture.get("execution_ready") is False,
            "FRESH_UNSIGNED_CAPTURE_INVALID")
    require(simulation_closure.get("status") ==
            "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED"
            and simulation_closure.get("closure_id") == generated.get("closure_id")
            and simulation_closure.get("message_sha256") ==
                capture.get("message_sha256")
            and simulation_closure.get("transaction_sha256") ==
                capture.get("transaction_sha256")
            and simulation_closure.get("gross_claim_raw") == "5000"
            and simulation_closure.get("partner_delta_raw") == "4000"
            and simulation_closure.get("project_admin_delta_raw") == "1000"
            and simulation_closure.get("claim_execution_approved") is False,
            "FRESH_SIMULATION_CLOSURE_INVALID")
    require(gate.get("status") == "ARMED"
            and gate.get("gate_id") == generated.get("gate_id")
            and gate.get("closure_id") == simulation_closure.get("closure_id")
            and gate.get("message_sha256") == capture.get("message_sha256")
            and gate.get("unsigned_transaction_sha256") ==
                capture.get("transaction_sha256")
            and gate.get("wallet_review_count") == 0
            and gate.get("approval_count") == 0
            and gate.get("submission_attempt_count") == 0
            and gate.get("submission_permitted") is False
            and gate.get("live_claim_approved") is False
            and gate.get("claim_submitted") is False
            and gate.get("execution_ready") is False,
            "FRESH_GATE_INVALID_OR_UNSAFE")
    require(gate.get("gate_id") != plan["retired_source_gate_id"]
            and capture.get("message_sha256") != plan["prior_message_sha256"]
            and simulation_closure.get("closure_id") !=
                evidence_closure.get("simulation_closure_id"),
            "PRIOR_CLAIM_MATERIAL_REUSED")
    gate_review_writer(gate_file, review_path)
    return {
        "status": "CLAIM_V2_FRESH_RECONSTRUCTION_PREPARED_REVIEW_REQUIRED",
        "evidence_closure_id": plan["evidence_closure_id"],
        "retired_source_gate_id": plan["retired_source_gate_id"],
        "fresh_gate_id": gate["gate_id"],
        "fresh_simulation_closure_id": simulation_closure["closure_id"],
        "fresh_message_sha256": capture["message_sha256"],
        "fresh_unsigned_transaction_sha256": capture["transaction_sha256"],
        "fresh_capture_slot": capture["rpc_slot"],
        "fresh_gate_review_created": True,
        "fresh_gate_status": "ARMED",
        "prior_gate_reused": False,
        "prior_message_reused": False,
        "prior_signed_transaction_reused": False,
        "transaction_constructed": True,
        "transaction_signed": False,
        "wallet_signature_verified": False,
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
    plan = commands.add_parser("plan")
    plan.add_argument("--evidence-closure", required=True)
    plan.add_argument("--boundary", required=True)
    plan.add_argument("--output", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--identity", required=True)
    prepare.add_argument("--evidence-closure", required=True)
    prepare.add_argument("--boundary", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument("--gate", required=True)
    prepare.add_argument("--confirm", required=True)
    prepare.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        require(not Path(args.output).exists(), "OUTPUT_ALREADY_EXISTS")
        closure = _read_json(args.evidence_closure)
        boundary = _read_json(args.boundary)
        if args.command == "plan":
            report = verify_reconstruction_plan(closure, boundary)
        else:
            report = prepare_fresh_reconstruction(
                _read_json(args.identity), closure, boundary,
                args.output_dir, args.gate, args.confirm)
        _write_exclusive(args.output, report)
        print(json.dumps(report, separators=(",", ":")))
        return 2
    except ClaimV2FreshReconstructionRejected as error:
        reason = str(error)
    except Exception:
        reason = "FRESH_RECONSTRUCTION_INPUT_OR_UPSTREAM_UNAVAILABLE"
    print(json.dumps({
        "status": "CLAIM_V2_FRESH_RECONSTRUCTION_NOT_VERIFIED",
        "reason": reason,
        "live_claim_approved": False,
        "submission_permitted": False,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
    }, separators=(",", ":")))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
