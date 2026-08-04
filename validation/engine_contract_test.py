"""
DexSato Engine Contract Test

Validate the public Intelligence Engine contract.

This validator verifies:

Observation
    ↓
Intelligence Engine
    ↓
Intelligence Package

No database.
No network.
No production writes.
"""

from engines.observation_builder import calculate_observation
from scanner.intelligence_engine import build_intelligence
from core.artifacts.decision_artifact import DecisionArtifact


def run():

    print("Running Engine Contract Test...\n")

    passed = 0
    failed = 0
    details = []

    # ---------------------------------------
    # Sample Market Events
    # ---------------------------------------

    previous = {
        "price": 100.0,
        "liquidity": 1000.0,
        "volume_24h": 500.0,
        "market_cap": 10000.0,
        "fdv": 10000.0,
    }

    current = {
        "price": 110.0,
        "liquidity": 1200.0,
        "volume_24h": 700.0,
        "market_cap": 11000.0,
        "fdv": 11000.0,
    }

    # ---------------------------------------
    # Observation
    # ---------------------------------------

    try:

        observation = calculate_observation(
            token="TEST",
            current=current,
            previous=previous,
        )

        assert isinstance(observation, dict)

        required_fields = (
            "token",
            "price_change_pct",
            "liquidity_change_pct",
            "volume_change_pct",
            "market_cap_change_pct",
            "fdv_change_pct",
        )

        for field in required_fields:
            assert field in observation

        print("[PASS] Observation Contract")

        details.append("Observation")

        passed += 1

    except Exception as e:

        print(f"[FAIL] Observation Contract ({e})")

        failed += 1

        return _result(passed, failed, details)

    # ---------------------------------------
    # Intelligence Engine
    # ---------------------------------------

    try:

        intelligence = build_intelligence(
            token="TEST",
            observation=observation,
        )

        assert isinstance(intelligence, dict)

        print("[PASS] Intelligence Package")

        details.append("Intelligence Package")

        passed += 1

    except Exception as e:

        print(f"[FAIL] Intelligence Package ({e})")

        failed += 1

        return _result(passed, failed, details)

    # ---------------------------------------
    # Contract Validation
    # ---------------------------------------

    try:

        required = (
            "token",
            "observation",
            "signals",
            "interpretations",
            "decision",
        )

        for field in required:
            assert field in intelligence

        assert isinstance(intelligence["signals"], list)
        assert isinstance(intelligence["interpretations"], list)
        assert isinstance(
            intelligence["decision"],
            DecisionArtifact,
        )

        print("[PASS] Engine Contract")

        details.append("Engine Contract")

        passed += 1

    except Exception as e:

        print(f"[FAIL] Engine Contract ({e})")

        failed += 1

        return _result(passed, failed, details)

    print()

    return _result(passed, failed, details)


def _result(passed, failed, details):

    return {

        "name": "Engine Contract Test",

        "status": "PASS" if failed == 0 else "FAIL",

        "passed": passed,

        "failed": failed,

        "details": details,

    }