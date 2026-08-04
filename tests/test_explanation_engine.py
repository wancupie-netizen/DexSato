"""
Tests for DexSato Explanation Engine.
"""

from scanner.models import PatternResult
from scanner.explanation_engine import build_explanation


def test_should_build_explanation_from_pattern():

    decision = {
        "decision": "WATCH",
        "confidence": "MEDIUM",
        "reasons": [],
    }

    patterns = [

        PatternResult(

            name="Bullish Escalation",

            confidence=0.95,

            description="",

        )

    ]

    explanation = build_explanation(

        decision,

        {

            "EARLY_MOMENTUM",

        },

        patterns,

    )

    assert explanation.summary == "Bullish Escalation detected."

    assert (
        explanation.recommendation
        == "Continue monitoring for confirmation."
    )

    assert "Bullish Escalation" in explanation.highlights

    assert "EARLY_MOMENTUM" in explanation.highlights


def test_should_support_empty_patterns():

    decision = {
        "decision": "IGNORE",
        "confidence": "LOW",
        "reasons": [],
    }

    explanation = build_explanation(

        decision,

        set(),

        [],

    )

    assert (
        explanation.summary
        == "No significant market behaviour detected."
    )

    assert (
        explanation.recommendation
        == "No immediate action is required."
    )

    assert explanation.highlights == []