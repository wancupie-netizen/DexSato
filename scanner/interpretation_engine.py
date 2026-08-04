"""
DexSato Interpretation Engine

Convert atomic market signals into market interpretations.

Responsibilities
----------------
- Read atomic signals
- Match interpretation rules
- Return market interpretations

This module does NOT:
- make decisions
- assign confidence
- generate narratives
"""

from scanner.signal_types import SignalType
from scanner.interpretation_types import InterpretationType


# --------------------------------------------------
# Interpretation Rules
# --------------------------------------------------

INTERPRETATION_RULES = {

    # ==================================================
    # MOMENTUM
    # ==================================================

    frozenset({
        SignalType.PRICE_UP,
        SignalType.VOLUME_UP,
    }): InterpretationType.EARLY_MOMENTUM,

    frozenset({
        SignalType.PRICE_UP,
        SignalType.VOLUME_UP,
        SignalType.LIQUIDITY_UP,
    }): InterpretationType.STRONG_MOMENTUM,

    frozenset({
        SignalType.PRICE_DOWN,
        SignalType.VOLUME_DOWN,
    }): InterpretationType.WEAK_MOMENTUM,

    frozenset({
        SignalType.PRICE_UP,
        SignalType.VOLUME_DOWN,
    }): InterpretationType.WEAK_BREAKOUT,

    # ==================================================
    # PARTICIPATION
    # ==================================================

    frozenset({
        SignalType.PRICE_STABLE,
        SignalType.VOLUME_UP,
    }): InterpretationType.ACCUMULATION,

    frozenset({
        SignalType.PRICE_DOWN,
        SignalType.VOLUME_UP,
    }): InterpretationType.DISTRIBUTION,

    frozenset({
        SignalType.PRICE_STABLE,
        SignalType.VOLUME_DOWN,
    }): InterpretationType.LOW_INTEREST,

    # ==================================================
    # LIQUIDITY
    # ==================================================

    frozenset({
        SignalType.LIQUIDITY_UP,
        SignalType.VOLUME_UP,
    }): InterpretationType.STRONG_LIQUIDITY,

    frozenset({
        SignalType.LIQUIDITY_DOWN,
        SignalType.VOLUME_UP,
    }): InterpretationType.RISKY_ACTIVITY,

    frozenset({
        SignalType.LIQUIDITY_DOWN,
        SignalType.PRICE_UP,
    }): InterpretationType.THIN_BREAKOUT,
}


def detect_interpretations(
    signals: set[SignalType],
) -> set[InterpretationType]:
    """
    Convert atomic signals into market interpretations.
    """

    interpretations: set[InterpretationType] = set()

    for required_signals, interpretation in INTERPRETATION_RULES.items():

        if required_signals.issubset(signals):
            interpretations.add(interpretation)

    return interpretations