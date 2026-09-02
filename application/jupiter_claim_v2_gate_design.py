"""Deterministic design-only contract for a future one-shot ClaimV2 gate.

No arm, persistence, signing, submission, RPC or state-transition operation is
implemented here.  This artifact cannot authorize or execute a claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_JSON_BYTES = 65_536
MAXIMUM_CLAIM_RAW = 5_000
GATE_TTL_SECONDS = 300
CONFIRMATION_PHRASE = "I APPROVE ONE CONTROLLED CLAIM V2"
PLANNED_STATES = (
    "DESIGN_ONLY", "APPROVAL_PENDING", "ARMED", "BOUND", "CONSUMED",
    "FINALIZATION_PENDING", "FINALIZED_VERIFIED", "FAILED", "EXPIRED",
)


class ClaimV2GateDesignRejected(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ClaimV2GateDesignRejected(code)


def design_one_shot_claim_gate(closure):
    require(type(closure) is dict and len(closure) <= 64,
            "INVALID_CLOSURE_CONTRACT")
    require(closure.get("status") == "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED"
            and closure.get("claim_gate_design_eligible") is True
            and closure.get("simulated_claim_split_verified") is True
            and closure.get("balance_conservation_verified") is True,
            "VERIFIED_SIMULATION_CLOSURE_REQUIRED")
    require(closure.get("claim_execution_approved") is False
            and closure.get("transaction_signed") is False
            and closure.get("transaction_submitted") is False
            and closure.get("claim_submitted") is False
            and closure.get("execution_ready") is False,
            "EXECUTION_EVIDENCE_FORBIDDEN")
    for field in ("closure_id", "message_sha256", "transaction_sha256"):
        value = closure.get(field)
        require(type(value) is str and len(value) == 64
                and all(char in "0123456789abcdef" for char in value),
                "INVALID_CLOSURE_HASH")
    require(closure.get("gross_claim_raw") == str(MAXIMUM_CLAIM_RAW)
            and closure.get("partner_delta_raw") == "4000"
            and closure.get("project_admin_delta_raw") == "1000",
            "CLAIM_AMOUNT_OR_SPLIT_MISMATCH")
    require(type(closure.get("mint")) is str
            and type(closure.get("referral_account")) is str
            and type(closure.get("partner")) is str,
            "CLAIM_IDENTITY_BINDING_REQUIRED")
    return {
        "status": "CLAIM_V2_ONE_SHOT_GATE_DESIGN_REVIEW_REQUIRED",
        "implementation_mode": "DESIGN_ONLY",
        "design_version": 1,
        "closure_id": closure["closure_id"],
        "message_sha256": closure["message_sha256"],
        "transaction_sha256": closure["transaction_sha256"],
        "mint": closure["mint"],
        "referral_account": closure["referral_account"],
        "partner": closure["partner"],
        "exact_claim_raw": str(MAXIMUM_CLAIM_RAW),
        "maximum_claim_raw": str(MAXIMUM_CLAIM_RAW),
        "expected_partner_raw": "4000",
        "expected_project_raw": "1000",
        "proposed_ttl_seconds": GATE_TTL_SECONDS,
        "required_confirmation_phrase": CONFIRMATION_PHRASE,
        "planned_states": list(PLANNED_STATES),
        "required_terminal_receipt": "FINALIZED_VERIFIED",
        "replay_policy": "ONE_ATTEMPT_IDENTICAL_STATUS_POLL_ONLY",
        "persistence_implemented": False,
        "arming_implemented": False,
        "wallet_signing_implemented": False,
        "transaction_submission_implemented": False,
        "live_claim_approved": False,
        "claim_execution_ready": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
        "note": "Design review only; no operational claim gate exists.",
    }


def read_json(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= MAX_JSON_BYTES, "JSON_TOO_LARGE")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8-sig"),
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except ClaimV2GateDesignRejected:
        raise
    except Exception:
        raise ClaimV2GateDesignRejected("INVALID_JSON_INPUT") from None
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    try:
        require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
        design = design_one_shot_claim_gate(read_json(args.closure))
        output.write_text(json.dumps(design, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: design[key] for key in
            ("status", "implementation_mode", "claim_execution_ready",
             "execution_ready")}))
        return 2
    except ClaimV2GateDesignRejected as error:
        reason = str(error)
    except Exception:
        reason = "GATE_DESIGN_INPUT_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status": "CLAIM_V2_GATE_DESIGN_NOT_VERIFIED",
        "reason": reason, "claim_execution_ready": False,
        "execution_ready": False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
