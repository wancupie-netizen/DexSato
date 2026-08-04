"""
Tests for DexSato Interpretation Engine.

Responsibilities
----------------
Verify that detect_interpretations() converts
market signals into the correct InterpretationType set.
"""

from scanner.interpretation_engine import detect_interpretations
from scanner.interpretation_types import InterpretationType
from scanner.signal_types import SignalType


# ==================================================
# Momentum
# ==================================================

def test_should_detect_early_momentum():

    signals = {
        SignalType.PRICE_UP,
        SignalType.VOLUME_UP,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.EARLY_MOMENTUM in result


def test_should_detect_strong_momentum():

    signals = {
        SignalType.PRICE_UP,
        SignalType.VOLUME_UP,
        SignalType.LIQUIDITY_UP,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.STRONG_MOMENTUM in result


def test_should_detect_weak_momentum():

    signals = {
        SignalType.PRICE_DOWN,
        SignalType.VOLUME_DOWN,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.WEAK_MOMENTUM in result


def test_should_detect_weak_breakout():

    signals = {
        SignalType.PRICE_UP,
        SignalType.VOLUME_DOWN,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.WEAK_BREAKOUT in result


# ==================================================
# Participation
# ==================================================

def test_should_detect_accumulation():

    signals = {
        SignalType.PRICE_STABLE,
        SignalType.VOLUME_UP,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.ACCUMULATION in result


def test_should_detect_distribution():

    signals = {
        SignalType.PRICE_DOWN,
        SignalType.VOLUME_UP,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.DISTRIBUTION in result


def test_should_detect_low_interest():

    signals = {
        SignalType.PRICE_STABLE,
        SignalType.VOLUME_DOWN,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.LOW_INTEREST in result


# ==================================================
# Liquidity
# ==================================================

def test_should_detect_strong_liquidity():

    signals = {
        SignalType.LIQUIDITY_UP,
        SignalType.VOLUME_UP,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.STRONG_LIQUIDITY in result


def test_should_detect_risky_activity():

    signals = {
        SignalType.LIQUIDITY_DOWN,
        SignalType.VOLUME_UP,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.RISKY_ACTIVITY in result


def test_should_detect_thin_breakout():

    signals = {
        SignalType.LIQUIDITY_DOWN,
        SignalType.PRICE_UP,
    }

    result = detect_interpretations(signals)

    assert InterpretationType.THIN_BREAKOUT in result


# ==================================================
# Edge Cases
# ==================================================

def test_should_return_empty_set_when_no_rules_match():

    signals = {
        SignalType.PRICE_STABLE,
        SignalType.VOLUME_STABLE,
    }

    result = detect_interpretations(signals)

    assert result == set()


def test_should_return_multiple_interpretations_when_rules_overlap():

    signals = {
        SignalType.PRICE_UP,
        SignalType.VOLUME_UP,
        SignalType.LIQUIDITY_UP,
    }

    result = detect_interpretations(signals)

    expected = {
        InterpretationType.EARLY_MOMENTUM,
        InterpretationType.STRONG_MOMENTUM,
        InterpretationType.STRONG_LIQUIDITY,
    }

    assert result == expected