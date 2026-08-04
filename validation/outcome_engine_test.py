"""
DexSato Outcome Engine Test

Validate Outcome Engine behaviour.

Responsibilities
----------------
- Verify approved GateResult is accepted.
- Verify rejected GateResult is rejected.
- Verify OutcomeArtifact is created correctly.

No network access.
No database access.
"""

from decimal import Decimal

from scanner.outcome_engine import record_outcome
from scanner.decision_gate import validate

from core.artifacts.decision_artifact import (
    DecisionArtifact,
    DecisionContext,
    DecisionMetadata,
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


# ==========================================================
# Individual Tests
# ==========================================================

def test_record_outcome():

    artifact = build_decision()

    gate = validate(artifact)

    snapshot = build_snapshot()

    outcome = record_outcome(

        gate_result=gate,

        market_snapshot=snapshot,

        observation_window="1h",

    )

    assert outcome.decision_artifact_id == artifact.artifact_id

    assert outcome.market_snapshot == snapshot

    assert outcome.observation_window == "1h"

    assert outcome.snapshot_status == "RECORDED"

    return True


def test_reject_unapproved_gate():

    artifact = build_decision()

    gate = validate(artifact)

    gate = type(gate)(
        status="REJECTED",
        artifact=gate.artifact,
        errors=gate.errors,
        metadata=gate.metadata,
    )

    snapshot = build_snapshot()

    try:

        record_outcome(

            gate_result=gate,

            market_snapshot=snapshot,

            observation_window="1h",

        )

    except ValueError:

        return True

    raise AssertionError(
        "Outcome Engine accepted rejected GateResult."
    )


# ==========================================================
# Runner
# ==========================================================

def run():

    print("Running Outcome Engine Test...\n")

    tests = [

        ("Record Outcome", test_record_outcome),

        ("Reject Unapproved Gate", test_reject_unapproved_gate),

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

        "name": "Outcome Engine Test",

        "status": "PASS" if failed == 0 else "FAIL",

        "passed": passed,

        "failed": failed,

        "details": details,

    }


if __name__ == "__main__":

    run()