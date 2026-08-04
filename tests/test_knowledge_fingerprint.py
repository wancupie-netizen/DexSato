"""
Tests for DexSato Knowledge Fingerprint.

Responsibilities
----------------
Verify that build_knowledge_fingerprint()
produces deterministic fingerprints.
"""

from scanner.knowledge_fingerprint import build_knowledge_fingerprint
from scanner.decision_types import DecisionType
from scanner.interpretation_types import InterpretationType


def build_package(decision, interpretations):

    return {
        "decision": {
            "decision": decision,
        },
        "interpretations": interpretations,
    }


# ==================================================
# Deterministic
# ==================================================

def test_should_generate_same_fingerprint_for_same_package():

    package = build_package(
        DecisionType.WATCH,
        {
            InterpretationType.ACCUMULATION,
        },
    )

    fp1 = build_knowledge_fingerprint(package)
    fp2 = build_knowledge_fingerprint(package)

    assert fp1 == fp2


# ==================================================
# Decision Change
# ==================================================

def test_should_change_fingerprint_when_decision_changes():

    fp1 = build_knowledge_fingerprint(
        build_package(
            DecisionType.IGNORE,
            {
                InterpretationType.LOW_INTEREST,
            },
        )
    )

    fp2 = build_knowledge_fingerprint(
        build_package(
            DecisionType.WATCH,
            {
                InterpretationType.LOW_INTEREST,
            },
        )
    )

    assert fp1 != fp2


# ==================================================
# Interpretation Change
# ==================================================

def test_should_change_fingerprint_when_interpretations_change():

    fp1 = build_knowledge_fingerprint(
        build_package(
            DecisionType.REVIEW,
            {
                InterpretationType.WEAK_MOMENTUM,
            },
        )
    )

    fp2 = build_knowledge_fingerprint(
        build_package(
            DecisionType.REVIEW,
            {
                InterpretationType.DISTRIBUTION,
            },
        )
    )

    assert fp1 != fp2


# ==================================================
# Order Independence
# ==================================================

def test_should_ignore_interpretation_order():

    fp1 = build_knowledge_fingerprint(
        build_package(
            DecisionType.REVIEW,
            {
                InterpretationType.DISTRIBUTION,
                InterpretationType.RISKY_ACTIVITY,
            },
        )
    )

    fp2 = build_knowledge_fingerprint(
        build_package(
            DecisionType.REVIEW,
            [
                InterpretationType.RISKY_ACTIVITY.value,
                InterpretationType.DISTRIBUTION.value,
            ],
        )
    )

    assert fp1 == fp2


# ==================================================
# Enum vs String
# ==================================================

def test_should_support_enum_and_string_inputs():

    fp1 = build_knowledge_fingerprint(
        build_package(
            DecisionType.WATCH,
            {
                InterpretationType.ACCUMULATION,
            },
        )
    )

    fp2 = build_knowledge_fingerprint(
        build_package(
            DecisionType.WATCH,
            [
                InterpretationType.ACCUMULATION.value,
            ],
        )
    )

    assert fp1 == fp2


# ==================================================
# Added Interpretation
# ==================================================

def test_should_change_fingerprint_when_interpretation_is_added():

    fp1 = build_knowledge_fingerprint(
        build_package(
            DecisionType.REVIEW,
            {
                InterpretationType.DISTRIBUTION,
            },
        )
    )

    fp2 = build_knowledge_fingerprint(
        build_package(
            DecisionType.REVIEW,
            {
                InterpretationType.DISTRIBUTION,
                InterpretationType.RISKY_ACTIVITY,
            },
        )
    )

    assert fp1 != fp2


# ==================================================
# Removed Interpretation
# ==================================================

def test_should_change_fingerprint_when_interpretation_is_removed():

    fp1 = build_knowledge_fingerprint(
        build_package(
            DecisionType.REVIEW,
            {
                InterpretationType.DISTRIBUTION,
                InterpretationType.RISKY_ACTIVITY,
            },
        )
    )

    fp2 = build_knowledge_fingerprint(
        build_package(
            DecisionType.REVIEW,
            {
                InterpretationType.DISTRIBUTION,
            },
        )
    )

    assert fp1 != fp2