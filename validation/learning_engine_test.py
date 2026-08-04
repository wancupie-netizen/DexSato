"""
DexSato Learning Engine Test

Validate Learning Engine behaviour.

Responsibilities
----------------
- Verify LearningArtifact is created correctly.
- Verify OutcomeArtifact is accepted.
- Verify invalid input is rejected.

No network access.
No database access.
"""

from decimal import Decimal

from scanner.learning_engine import build_learning

from core.artifacts.decision_artifact import (
    DecisionArtifact,
    DecisionContext,
    DecisionMetadata,
)

from core.artifacts.outcome_artifact import (
    OutcomeArtifact,
)

from core.models.market_snapshot import (
    MarketSnapshot,
)


# ==========================================================
# Test Builders
# ==========================================================

def build_decision() -> DecisionArtifact:

    return DecisionArtifact(

        recommended_action="ALERT",

        confidence=90,

        summary="Recommended action: ALERT",

        context=DecisionContext(),

        reasons=(),

        metadata=DecisionMetadata(
            engine_version="1.0.0",
            symbol="BTC",
            pair="BTC",
        ),
    )


def build_snapshot() -> MarketSnapshot:

    return MarketSnapshot(

        symbol="BTC",

        pair="BTC/USDT",

        chain="Bitcoin",

        price=Decimal("100000"),

        liquidity=Decimal("5000000"),

        volume_24h=Decimal("25000000"),

        provider="Unit Test",
    )


def build_outcome() -> OutcomeArtifact:

    decision = build_decision()

    snapshot = build_snapshot()

    return OutcomeArtifact.from_decision(

        decision=decision,

        market_snapshot=snapshot,

        observation_window="1h",

        snapshot_status="RECORDED",

    )


# ==========================================================
# Individual Tests
# ==========================================================

def test_build_learning():

    outcome = build_outcome()

    learning = build_learning(outcome)

    assert learning.outcome_artifact_id == outcome.artifact_id

    assert learning.learning_status == "CONFIRMED"

    assert learning.summary == "Outcome recorded successfully."

    return True


def test_invalid_outcome():

    try:

        build_learning(None)

    except ValueError:

        return True

    raise AssertionError(
        "Learning Engine accepted None OutcomeArtifact."
    )


# ==========================================================
# Runner
# ==========================================================

def run():

    print("Running Learning Engine Test...\n")

    tests = [

        ("Build Learning", test_build_learning),

        ("Reject Invalid Outcome", test_invalid_outcome),

    ]

    passed = 0
    failed = 0

    details = []

    for name, test in tests:

        try:

            test()

            print(f"[PASS] {name}")

            details.append(name)

            passed += 1

        except Exception as e:

            print(f"[FAIL] {name}")

            print(f"       {e}")

            failed += 1

    print()

    return {

        "name": "Learning Engine Test",

        "status": "PASS" if failed == 0 else "FAIL",

        "passed": passed,

        "failed": failed,

        "details": details,

    }


if __name__ == "__main__":

    run()