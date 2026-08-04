"""
Tests for DexSato Pattern Engine.
"""

from scanner.pattern_engine import detect_patterns
from scanner.models import PatternResult


def build_event(decision):

    return {
        "decision": decision,
        "confidence": "MEDIUM",
    }


# ==================================================
# Empty History
# ==================================================

def test_should_return_empty_when_history_is_empty():

    patterns = detect_patterns([])

    assert patterns == []


# ==================================================
# Not Enough History
# ==================================================

def test_should_return_empty_when_history_is_too_short():

    history = [

        build_event("WATCH"),

        build_event("WATCH"),

    ]

    patterns = detect_patterns(history)

    assert patterns == []


# ==================================================
# Persistent Watch
# ==================================================

def test_should_detect_persistent_watch():

    history = [

        build_event("WATCH"),

        build_event("WATCH"),

        build_event("WATCH"),

    ]

    patterns = detect_patterns(history)

    assert len(patterns) == 1

    pattern = patterns[0]

    assert isinstance(
        pattern,
        PatternResult,
    )

    assert pattern.name == "Persistent Watch"

    assert pattern.confidence == 0.90


# ==================================================
# Bullish Escalation
# ==================================================

def test_should_detect_bullish_escalation():

    history = [

        build_event("WATCH"),

        build_event("REVIEW"),

        build_event("IGNORE"),

    ]

    patterns = detect_patterns(history)

    assert len(patterns) == 1

    assert patterns[0].name == "Bullish Escalation"

    assert patterns[0].confidence == 0.95


# ==================================================
# Bearish Deterioration
# ==================================================

def test_should_detect_bearish_deterioration():

    history = [

        build_event("IGNORE"),

        build_event("REVIEW"),

        build_event("WATCH"),

    ]

    patterns = detect_patterns(history)

    assert len(patterns) == 1

    assert patterns[0].name == "Bearish Deterioration"

    assert patterns[0].confidence == 0.95


# ==================================================
# Oscillation
# ==================================================

def test_should_detect_oscillation():

    history = [

        build_event("WATCH"),

        build_event("REVIEW"),

        build_event("WATCH"),

    ]

    patterns = detect_patterns(history)

    assert len(patterns) == 1

    assert patterns[0].name == "Oscillation"

    assert patterns[0].confidence == 0.85


# ==================================================
# No Pattern
# ==================================================

def test_should_not_detect_any_pattern():

    history = [

        build_event("ALERT"),

        build_event("WATCH"),

        build_event("IGNORE"),

    ]

    patterns = detect_patterns(history)

    assert patterns == []