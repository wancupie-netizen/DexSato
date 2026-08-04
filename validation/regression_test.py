"""
DexSato Regression Test

Validate engine behaviour against the official
Golden Dataset.

Regression Test verifies:

Observation
    ↓
Intelligence Engine
    ↓
DecisionArtifact
    ↓
Expected Result

This validator performs:

- No network access
- No database access
- No production writes
"""

import json
from pathlib import Path

from scanner.intelligence_engine import build_intelligence


FIXTURE_DIR = Path(__file__).parent / "fixtures"
EXPECTED_DIR = Path(__file__).parent / "expected"


def _load_json(path: Path):

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _compare(case_name, intelligence, expected):

    decision = intelligence["decision"]

    errors = []

    # ----------------------------------
    # Recommended Action
    # ----------------------------------

    if decision.recommended_action != expected["recommended_action"]:

        errors.append(
            f"recommended_action "
            f"expected={expected['recommended_action']} "
            f"actual={decision.recommended_action}"
        )

    # ----------------------------------
    # Confidence
    # ----------------------------------

    if decision.confidence != expected["confidence"]:

        errors.append(
            f"confidence "
            f"expected={expected['confidence']} "
            f"actual={decision.confidence}"
        )

    # ----------------------------------
    # Interpretations
    # ----------------------------------

    actual_interpretations = sorted(
        intelligence["interpretations"]
    )

    expected_interpretations = sorted(
        expected["interpretations"]
    )

    if actual_interpretations != expected_interpretations:

        errors.append(
            "interpretations mismatch"
        )

    return errors


def run():

    print("Running Regression Test...\n")

    passed = 0
    failed = 0

    details = []

    fixture_files = sorted(
        FIXTURE_DIR.glob("*_case.json")
    )

    for fixture_file in fixture_files:

        case_name = fixture_file.stem.replace("_case", "")

        expected_file = (
            EXPECTED_DIR /
            f"{case_name}_expected.json"
        )

        if not expected_file.exists():

            print(f"[FAIL] {case_name.upper()}")

            print("       Missing expected file")

            failed += 1

            continue

        fixture = _load_json(fixture_file)

        expected = _load_json(expected_file)

        intelligence = build_intelligence(
            token=fixture["token"],
            observation=fixture["observation"],
        )

        errors = _compare(
            case_name,
            intelligence,
            expected,
        )

        if errors:

            print(f"[FAIL] {case_name.upper()}")

            for error in errors:

                print(f"       {error}")

            failed += 1

        else:

            print(f"[PASS] {case_name.upper()}")

            details.append(case_name.upper())

            passed += 1

    print()

    return {

        "name": "Regression Test",

        "status": "PASS" if failed == 0 else "FAIL",

        "passed": passed,

        "failed": failed,

        "details": details,

    }