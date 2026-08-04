"""
Tests for DexSato Intelligence Engine.
"""

from unittest.mock import patch

from scanner.intelligence_engine import build_intelligence


@patch("scanner.intelligence_engine.make_decision")
@patch("scanner.intelligence_engine.detect_interpretations")
@patch("scanner.intelligence_engine.detect_signals")
def test_should_build_complete_package(

    mock_detect_signals,
    mock_detect_interpretations,
    mock_make_decision,

):

    observation = {
        "token": "BTC",
    }

    mock_detect_signals.return_value = {
        "EARLY_PRICE_UP",
    }

    mock_detect_interpretations.return_value = {
        "EARLY_MOMENTUM",
    }

    mock_make_decision.return_value = {
        "decision": "WATCH",
        "confidence": "MEDIUM",
        "reasons": [],
    }

    package = build_intelligence(
        "BTC",
        observation,
    )

    assert package["token"] == "BTC"

    assert package["observation"] == observation

    assert package["signals"] == [
        "EARLY_PRICE_UP",
    ]

    assert package["interpretations"] == [
        "EARLY_MOMENTUM",
    ]

    assert package["decision"]["decision"] == "WATCH"