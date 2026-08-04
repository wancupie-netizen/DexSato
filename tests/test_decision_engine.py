"""
Tests for DexSato Decision Engine.

Responsibilities
----------------
Verify that make_decision() converts market
interpretations into the correct Decision payload.
"""

from scanner.decision_engine import make_decision

from scanner.decision_types import (
    DecisionType,
    DECISION_CONFIDENCE,
)

from scanner.interpretation_types import InterpretationType


# ==================================================
# Default Behaviour
# ==================================================

def test_should_return_ignore_when_no_interpretations():

    result = make_decision(set())

    assert result["decision"] == DecisionType.IGNORE
    assert result["confidence"] == DECISION_CONFIDENCE[
        DecisionType.IGNORE
    ]
    assert result["reasons"] == []


# ==================================================
# Single Interpretation
# ==================================================

def test_should_return_watch_for_early_momentum():

    result = make_decision({
        InterpretationType.EARLY_MOMENTUM,
    })

    assert result["decision"] == DecisionType.WATCH
    assert result["confidence"] == DECISION_CONFIDENCE[
        DecisionType.WATCH
    ]
    assert result["reasons"] == [
        InterpretationType.EARLY_MOMENTUM.value
    ]


def test_should_return_alert_for_strong_momentum():

    result = make_decision({
        InterpretationType.STRONG_MOMENTUM,
    })

    assert result["decision"] == DecisionType.ALERT
    assert result["confidence"] == DECISION_CONFIDENCE[
        DecisionType.ALERT
    ]


def test_should_return_review_for_weak_breakout():

    result = make_decision({
        InterpretationType.WEAK_BREAKOUT,
    })

    assert result["decision"] == DecisionType.REVIEW
    assert result["confidence"] == DECISION_CONFIDENCE[
        DecisionType.REVIEW
    ]


def test_should_return_ignore_for_low_interest():

    result = make_decision({
        InterpretationType.LOW_INTEREST,
    })

    assert result["decision"] == DecisionType.IGNORE
    assert result["confidence"] == DECISION_CONFIDENCE[
        DecisionType.IGNORE
    ]


# ==================================================
# Decision Priority
# ==================================================

def test_should_choose_highest_priority_decision():

    result = make_decision({

        InterpretationType.STRONG_MOMENTUM,   # ALERT

        InterpretationType.LOW_INTEREST,      # IGNORE

        InterpretationType.ACCUMULATION,      # WATCH

    })

    assert result["decision"] == DecisionType.ALERT
    assert result["confidence"] == DECISION_CONFIDENCE[
        DecisionType.ALERT
    ]


def test_should_keep_watch_when_all_candidates_are_watch():

    result = make_decision({

        InterpretationType.EARLY_MOMENTUM,

        InterpretationType.ACCUMULATION,

    })

    assert result["decision"] == DecisionType.WATCH


def test_should_keep_review_when_all_candidates_are_review():

    result = make_decision({

        InterpretationType.WEAK_BREAKOUT,

        InterpretationType.WEAK_MOMENTUM,

    })

    assert result["decision"] == DecisionType.REVIEW


# ==================================================
# Reasons
# ==================================================

def test_should_return_sorted_reasons():

    result = make_decision({

        InterpretationType.RISKY_ACTIVITY,

        InterpretationType.DISTRIBUTION,

    })

    assert result["reasons"] == sorted([
        InterpretationType.RISKY_ACTIVITY.value,
        InterpretationType.DISTRIBUTION.value,
    ])


# ==================================================
# Unknown Interpretation
# ==================================================

def test_should_ignore_unknown_interpretations():

    class FakeInterpretation:
        value = "UNKNOWN"

    result = make_decision({
        FakeInterpretation(),
    })

    assert result["decision"] == DecisionType.IGNORE
    assert result["confidence"] == DECISION_CONFIDENCE[
        DecisionType.IGNORE
    ]
    assert result["reasons"] == []