"""
DexSato Decision Gate Test

Validate Decision Gate behaviour.

This validator verifies that Decision Gate
correctly accepts valid DecisionArtifacts
and rejects invalid ones.

No network access.
No database access.
No external dependencies.
"""

from scanner.decision_gate import validate

from core.artifacts.decision_artifact import (
    DecisionArtifact,
    DecisionContext,
    DecisionMetadata,
)


# ==========================================================
# Test Artifact Builder
# ==========================================================

def build_valid_artifact() -> DecisionArtifact:

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


# ==========================================================
# Individual Tests
# ==========================================================

def test_valid_artifact():

    artifact = build_valid_artifact()

    result = validate(artifact)

    assert result.approved
    assert result.status == "APPROVED"

    return True


def test_invalid_object():

    result = validate({})

    assert result.rejected
    assert result.status == "REJECTED"

    return True


def test_missing_summary():

    artifact = DecisionArtifact(

        recommended_action="ALERT",

        confidence=90,

        summary=None,

        context=DecisionContext(),

        reasons=(),

        metadata=DecisionMetadata(
            engine_version="1.0.0",
            symbol="BTC",
            pair="BTC",
        ),
    )

    result = validate(artifact)

    assert result.rejected

    return True


def test_empty_summary():

    artifact = DecisionArtifact(

        recommended_action="ALERT",

        confidence=90,

        summary="",

        context=DecisionContext(),

        reasons=(),

        metadata=DecisionMetadata(
            engine_version="1.0.0",
            symbol="BTC",
            pair="BTC",
        ),
    )

    result = validate(artifact)

    assert result.rejected

    return True


# ==========================================================
# Runner
# ==========================================================

def run():

    print("Running Decision Gate Test...\n")

    tests = [

        ("Valid DecisionArtifact", test_valid_artifact),

        ("Invalid Object", test_invalid_object),

        ("Missing Summary", test_missing_summary),

        ("Empty Summary", test_empty_summary),

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

        "name": "Decision Gate Test",

        "status": "PASS" if failed == 0 else "FAIL",

        "passed": passed,

        "failed": failed,

        "details": details,

    }


if __name__ == "__main__":

    run()