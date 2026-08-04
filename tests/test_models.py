"""
Tests for DexSato models.
"""

from scanner.models import ExplanationResult


def test_should_create_explanation_result():

    explanation = ExplanationResult(

        summary="Momentum is strengthening.",

        recommendation="Continue monitoring.",

        highlights=[

            "Bullish Escalation",

            "Strong Liquidity",

        ],

    )

    assert explanation.summary == "Momentum is strengthening."

    assert explanation.recommendation == "Continue monitoring."

    assert explanation.highlights == [

        "Bullish Escalation",

        "Strong Liquidity",

    ]