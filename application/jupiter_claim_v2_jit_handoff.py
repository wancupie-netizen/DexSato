"""Create a fresh ClaimV2 reconstruction only at an explicit sign-now handoff."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from application.jupiter_claim_v2_artifact_workflow import ARTIFACT_NAMES
from application.jupiter_claim_v2_fresh_approval import (
    MAX_CAPTURE_SLOT_AGE,
    inspect_fresh_capture,
)
from application.jupiter_claim_v2_fresh_reconstruction import (
    ClaimV2FreshReconstructionRejected,
    _read_json,
    _write_exclusive,
    prepare_fresh_reconstruction,
    require,
)
from application.jupiter_claim_v2_one_shot_gate import read_gate, write_gate
from application.jupiter_claim_v2_blockhash_attestation import attest_blockhash


HANDOFF_CONFIRMATION = "I AM READY TO SIGN FRESH CLAIM V2 NOW"
MAX_HANDOFF_SLOT_AGE = 4


def prepare_jit_handoff(identity, evidence_closure, boundary, output_dir,
                        gate_path, gate_confirmation, handoff_confirmation,
                        *, environment=None, generator=None, post=None):
    """Build once, then prove enough of the unchanged 32-slot window remains."""
    env = os.environ if environment is None else environment
    require(handoff_confirmation == HANDOFF_CONFIRMATION,
            "EXPLICIT_SIGN_NOW_HANDOFF_REQUIRED")
    require(env.get("DEXSATO_JUPITER_CLAIM_GATE_ENABLED", "false")
            .strip().lower() == "true", "CLAIM_GATE_FEATURE_REQUIRED")
    require(env.get("DEXSATO_JUPITER_CLAIM_LIVE_APPROVAL_ENABLED", "false")
            .strip().lower() == "false", "KEEP_LIVE_APPROVAL_DISABLED")
    require(env.get("DEXSATO_JUPITER_CLAIM_SUBMISSION_ENABLED", "false")
            .strip().lower() == "false", "KEEP_SUBMISSION_DISABLED")
    require(env.get("DEXSATO_JUPITER_FEE_ENABLED", "false")
            .strip().lower() == "false", "KEEP_PRODUCTION_FEES_DISABLED")

    kwargs = {"environment": env}
    if generator is not None:
        kwargs["generator"] = generator
    prepared = prepare_fresh_reconstruction(
        identity, evidence_closure, boundary, output_dir, gate_path,
        gate_confirmation, **kwargs)
    output = Path(output_dir)
    capture = _read_json(output / ARTIFACT_NAMES["capture"])
    closure = _read_json(output / ARTIFACT_NAMES["closure"])
    try:
        attestation = attest_blockhash(
            gate_path, closure, capture, environment=env, post=post)
    except Exception:
        stale_gate = read_gate(gate_path)
        require(stale_gate.get("status") == "ARMED"
                and stale_gate.get("approval_count") == 0
                and stale_gate.get("submission_attempt_count") == 0,
                "JIT_HANDOFF_GATE_INVALID")
        stale_gate.update(
            status="JIT_HANDOFF_RETIRED",
            submission_permitted=False,
            live_claim_approved=False,
            claim_execution_ready=False,
            execution_ready=False,
            jit_retirement_reason="POST_SIMULATION_BLOCKHASH_NOT_ATTESTED",
        )
        write_gate(gate_path, stale_gate)
        raise ClaimV2FreshReconstructionRejected(
            "POST_SIMULATION_BLOCKHASH_NOT_ATTESTED")
    gate = read_gate(gate_path)
    require(gate.get("status") == "ARMED"
            and gate.get("approval_count") == 0
            and gate.get("submission_attempt_count") == 0,
            "JIT_HANDOFF_GATE_INVALID")
    return {
        **prepared,
        "status": "CLAIM_V2_JIT_SIGNING_HANDOFF_READY",
        "handoff_capture_slot": capture["rpc_slot"],
        "handoff_current_slot": attestation["attestation_slot"],
        "handoff_slot_age": 0,
        "maximum_capture_slot_age": MAX_CAPTURE_SLOT_AGE,
        "remaining_slot_budget": MAX_CAPTURE_SLOT_AGE,
        "blockhash_attestation": attestation,
        "operator_action": "SIGN_IMMEDIATELY",
        "gate_consumed": False,
        "live_claim_approved": False,
        "submission_permitted": False,
        "submission_attempt_count": 0,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--evidence-closure", required=True)
    parser.add_argument("--boundary", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--gate-confirm", required=True)
    parser.add_argument("--handoff-confirm", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        require(not Path(args.output).exists(), "OUTPUT_ALREADY_EXISTS")
        report = prepare_jit_handoff(
            _read_json(args.identity), _read_json(args.evidence_closure),
            _read_json(args.boundary), args.output_dir, args.gate,
            args.gate_confirm, args.handoff_confirm)
        _write_exclusive(args.output, report)
        print(json.dumps(report, separators=(",", ":")))
        return 2
    except ClaimV2FreshReconstructionRejected as error:
        reason = str(error)
    except Exception:
        reason = "JIT_HANDOFF_INPUT_OR_UPSTREAM_UNAVAILABLE"
    print(json.dumps({
        "status": "CLAIM_V2_JIT_SIGNING_HANDOFF_NOT_VERIFIED",
        "reason": reason,
        "live_claim_approved": False,
        "submission_attempt_count": 0,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
    }, separators=(",", ":")))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
