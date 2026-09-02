"""Close fresh funded ClaimV2 simulation evidence without enabling execution."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MAX_JSON_BYTES = 262_144
EXPECTED_SDK_VERSION = "0.3.0"
EXPECTED_ORDER_AUTHORITY = "PINNED_SDK_COMPILED_IDL"
EXPECTED_GROSS_RAW = 5_000
EXPECTED_PARTNER_RAW = 4_000
EXPECTED_PROJECT_RAW = 1_000


class ClaimV2ClosureRejected(ValueError):
    """Fixed public rejection code; evidence content is never echoed."""


def require(condition, code):
    if not condition:
        raise ClaimV2ClosureRejected(code)


def _dict(value, code):
    require(type(value) is dict and len(value) <= 80, code)
    return value


def _hash(value, code):
    require(type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value), code)
    return value


def _amount(value, code):
    require(type(value) is str and value.isdigit() and len(value) <= 40, code)
    amount = int(value)
    require(0 <= amount < 2**64, code)
    return amount


def _safe_flags(report):
    for name in ("transaction_signed", "transaction_submitted", "claim_submitted",
                 "production_fee_execution_enabled", "execution_ready",
                 "fee_receipt_verified", "on_chain_receipt_verified"):
        require(report.get(name) is False, "EXECUTION_EVIDENCE_FORBIDDEN")


def close_funded_simulation(capture, binding, auxiliary, simulation):
    """Bind the reviewed artifacts into one deterministic closure record."""
    capture = _dict(capture, "INVALID_CAPTURE_EVIDENCE")
    binding = _dict(binding, "INVALID_BINDING_EVIDENCE")
    auxiliary = _dict(auxiliary, "INVALID_AUXILIARY_EVIDENCE")
    simulation = _dict(simulation, "INVALID_SIMULATION_EVIDENCE")
    require(capture.get("status") == "SDK_UNSIGNED_CAPTURED"
            and capture.get("sdk_version") == EXPECTED_SDK_VERSION
            and capture.get("execution_ready") is False
            and capture.get("fee_receipt_verified") is False,
            "FRESH_UNSIGNED_CAPTURE_REQUIRED")
    require(binding.get("status") == "PINNED_SDK_CLAIM_V2_CAPTURE_REVIEW_REQUIRED"
            and binding.get("compiled_account_binding_verified") is True
            and binding.get("sdk_version") == EXPECTED_SDK_VERSION
            and binding.get("account_order_authority", EXPECTED_ORDER_AUTHORITY)
                == EXPECTED_ORDER_AUTHORITY
            and binding.get("execution_ready") is False
            and binding.get("fee_receipt_verified") is False,
            "COMPILED_BINDING_REQUIRED")
    require(auxiliary.get("status") ==
            "CLAIM_V2_AUXILIARY_ALLOWLIST_REVIEW_REQUIRED"
            and auxiliary.get("auxiliary_instruction_semantics_verified") is True
            and auxiliary.get("execution_ready") is False
            and auxiliary.get("fee_receipt_verified") is False,
            "AUXILIARY_ALLOWLIST_REQUIRED")
    require(simulation.get("status") ==
            "CLAIM_V2_SIMULATION_BALANCE_DELTA_REVIEW_REQUIRED"
            and simulation.get("simulation_only") is True
            and simulation.get("simulated_claim_split_verified") is True
            and simulation.get("balance_conservation_verified") is True,
            "VERIFIED_FUNDED_SIMULATION_REQUIRED")
    _safe_flags(simulation)

    message_hash = _hash(capture.get("message_sha256"), "INVALID_MESSAGE_HASH")
    transaction_hash = _hash(capture.get("transaction_sha256"),
                             "INVALID_TRANSACTION_HASH")
    for report in (binding, auxiliary):
        require(report.get("message_sha256") == message_hash
                and report.get("transaction_sha256") == transaction_hash,
                "EVIDENCE_HASH_BINDING_MISMATCH")
    require(simulation.get("message_sha256") == message_hash,
            "SIMULATION_MESSAGE_BINDING_MISMATCH")
    require(simulation.get("sdk_version") == EXPECTED_SDK_VERSION
            and simulation.get("account_order_authority") == EXPECTED_ORDER_AUTHORITY,
            "SIMULATION_CONTRACT_PIN_MISMATCH")

    capture_slot = capture.get("rpc_slot")
    simulation_slot = simulation.get("simulation_slot")
    require(type(capture_slot) is int and capture_slot > 0
            and simulation.get("capture_slot") == capture_slot,
            "CAPTURE_SLOT_MISMATCH")
    require(type(simulation_slot) is int and simulation_slot >= capture_slot,
            "SIMULATION_SLOT_MISMATCH")

    referral_pre = _amount(simulation.get("referral_pre_raw"), "INVALID_REFERRAL_PRE")
    referral_post = _amount(simulation.get("referral_post_raw"), "INVALID_REFERRAL_POST")
    gross = _amount(simulation.get("gross_claim_raw"), "INVALID_GROSS_CLAIM")
    partner = _amount(simulation.get("partner_delta_raw"), "INVALID_PARTNER_DELTA")
    project = _amount(simulation.get("project_admin_delta_raw"),
                      "INVALID_PROJECT_DELTA")
    require((referral_pre, referral_post, gross, partner, project) ==
            (EXPECTED_GROSS_RAW, 0, EXPECTED_GROSS_RAW,
             EXPECTED_PARTNER_RAW, EXPECTED_PROJECT_RAW),
            "FUNDED_CLAIM_DELTA_MISMATCH")
    require(referral_pre - referral_post == gross
            and gross == partner + project
            and partner == gross * 8000 // 10_000,
            "CLAIM_SPLIT_CONSERVATION_MISMATCH")
    require(simulation.get("partner_pre_source") == "CREATED_ATA_IMPLICIT_ZERO",
            "PARTNER_ATA_LIFECYCLE_EVIDENCE_REQUIRED")

    identity = _dict(capture.get("identity"), "INVALID_CAPTURE_IDENTITY")
    mint = identity.get("mint")
    require(type(mint) is str and simulation.get("mint") == mint,
            "CLAIM_MINT_BINDING_MISMATCH")
    bound = {
        "message_sha256": message_hash,
        "transaction_sha256": transaction_hash,
        "capture_slot": capture_slot,
        "simulation_slot": simulation_slot,
        "mint": mint,
        "referral_account": identity.get("referral_account"),
        "partner": identity.get("partner"),
        "gross_claim_raw": str(gross),
        "partner_delta_raw": str(partner),
        "project_admin_delta_raw": str(project),
    }
    closure_id = hashlib.sha256(json.dumps(bound, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    return {
        "status": "FRESH_FUNDED_CLAIM_V2_SIMULATION_CLOSED",
        "closure_id": closure_id,
        **bound,
        "referral_post_raw": "0",
        "partner_pre_source": "CREATED_ATA_IMPLICIT_ZERO",
        "claim_split_bps": {"partner": 8000, "project": 2000},
        "compiled_account_binding_verified": True,
        "auxiliary_allowlist_verified": True,
        "simulated_claim_split_verified": True,
        "balance_conservation_verified": True,
        "simulation_only": True,
        "claim_gate_design_eligible": True,
        "claim_execution_approved": False,
        "transaction_signed": False,
        "transaction_submitted": False,
        "claim_submitted": False,
        "execution_ready": False,
        "fee_receipt_verified": False,
        "note": "Closure evidence is not a live ClaimV2 approval.",
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
        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except ClaimV2ClosureRejected:
        raise
    except Exception:
        raise ClaimV2ClosureRejected("INVALID_JSON_INPUT") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True)
    parser.add_argument("--binding-report", required=True)
    parser.add_argument("--auxiliary-report", required=True)
    parser.add_argument("--simulation-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    try:
        require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
        report = close_funded_simulation(read_json(args.capture),
            read_json(args.binding_report), read_json(args.auxiliary_report),
            read_json(args.simulation_report))
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: report[key] for key in
            ("status", "closure_id", "claim_execution_approved", "execution_ready")}))
        return 2
    except ClaimV2ClosureRejected as error:
        reason = str(error)
    except Exception:
        reason = "CLOSURE_INPUT_OR_OUTPUT_UNAVAILABLE"
    print(json.dumps({"status": "CLAIM_V2_SIMULATION_CLOSURE_NOT_VERIFIED",
        "reason": reason, "claim_execution_approved": False,
        "execution_ready": False}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
