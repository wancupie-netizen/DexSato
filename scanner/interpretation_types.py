"""
DexSato Interpretation Types

Interpretations represent the meaning derived from one or more
atomic market signals.

Interpretations are NOT:
- trading recommendations
- predictions
- AI-generated opinions

They are structured market intelligence.
"""

from enum import StrEnum


class InterpretationType(StrEnum):

    # ==================================================
    # Momentum
    # ==================================================

    EARLY_MOMENTUM = "EARLY_MOMENTUM"
    STRONG_MOMENTUM = "STRONG_MOMENTUM"
    WEAK_MOMENTUM = "WEAK_MOMENTUM"
    WEAK_BREAKOUT = "WEAK_BREAKOUT"

    # ==================================================
    # Participation
    # ==================================================

    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"
    LOW_INTEREST = "LOW_INTEREST"

    # ==================================================
    # Liquidity
    # ==================================================

    STRONG_LIQUIDITY = "STRONG_LIQUIDITY"
    WEAK_LIQUIDITY = "WEAK_LIQUIDITY"
    RISKY_ACTIVITY = "RISKY_ACTIVITY"
    THIN_BREAKOUT = "THIN_BREAKOUT"

    # ==================================================
    # Market Activity
    # ==================================================

    LOW_ACTIVITY = "LOW_ACTIVITY"

    # ==================================================
    # Market Structure
    # ==================================================

    BREAKOUT_CONDITIONS = "BREAKOUT_CONDITIONS"
    REVERSAL_CONDITIONS = "REVERSAL_CONDITIONS"

    # ==================================================
    # Risk
    # ==================================================

    HIGH_VOLATILITY = "HIGH_VOLATILITY"