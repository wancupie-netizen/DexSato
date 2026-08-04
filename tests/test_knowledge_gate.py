"""
Tests for DexSato Knowledge Gate.

Responsibilities
----------------
Verify that should_store() correctly decides
whether an Intelligence Package should become
persistent knowledge.
"""

from scanner.knowledge_gate import should_store
from scanner.interpretation_types import InterpretationType
from scanner.decision_types import DecisionType


def build_package(decision, interpretations):

    return {
        "decision": {
            "decision": decision,
        },
        "interpretations": interpretations,
    }


# ==================================================
# First Knowledge
# ==================================================

def test_should_store_first_knowledge():

    current = build_package(
        DecisionType.IGNORE,
        [],
    )

    assert should_store(current, None) is True


# ==================================================
# Decision Change
# ==================================================

def test_should_store_when_decision_changes():

    current = build_package(
        DecisionType.WATCH,
        [],
    )

    previous = build_package(
        DecisionType.IGNORE,
        [],
    )

    assert should_store(current, previous) is True


# ==================================================
# Interpretation Change
# ==================================================

def test_should_store_when_interpretations_change():

    current = build_package(
        DecisionType.REVIEW,
        {
            InterpretationType.DISTRIBUTION,
        },
    )

    previous = build_package(
        DecisionType.REVIEW,
        [
            InterpretationType.WEAK_MOMENTUM.value,
        ],
    )

    assert should_store(current, previous) is True


# ==================================================
# No Change
# ==================================================

def test_should_not_store_when_nothing_changes():

    current = build_package(
        DecisionType.REVIEW,
        {
            InterpretationType.DISTRIBUTION,
            InterpretationType.RISKY_ACTIVITY,
        },
    )

    previous = build_package(
        DecisionType.REVIEW,
        [
            InterpretationType.DISTRIBUTION.value,
            InterpretationType.RISKY_ACTIVITY.value,
        ],
    )

    assert should_store(current, previous) is False


# ==================================================
# Enum vs String
# ==================================================

def test_should_support_enum_and_string_interpretations():

    current = build_package(
        DecisionType.WATCH,
        {
            InterpretationType.ACCUMULATION,
        },
    )

    previous = build_package(
        DecisionType.WATCH,
        [
            InterpretationType.ACCUMULATION.value,
        ],
    )

    assert should_store(current, previous) is False


# ==================================================
# Order Independence
# ==================================================

def test_should_ignore_interpretation_order():

    current = build_package(
        DecisionType.REVIEW,
        {
            InterpretationType.DISTRIBUTION,
            InterpretationType.RISKY_ACTIVITY,
        },
    )

    previous = build_package(
        DecisionType.REVIEW,
        [
            InterpretationType.RISKY_ACTIVITY.value,
            InterpretationType.DISTRIBUTION.value,
        ],
    )

    assert should_store(current, previous) is False


# ==================================================
# Previous Empty
# ==================================================

def test_should_store_when_previous_has_no_interpretations():

    current = build_package(
        DecisionType.WATCH,
        {
            InterpretationType.ACCUMULATION,
        },
    )

    previous = build_package(
        DecisionType.WATCH,
        [],
    )

    assert should_store(current, previous) is True