# scanner/signal_types.py

"""
DexSato Signal Types

Atomic signals produced by Signal Detector.

Signals represent facts only.

They do NOT represent:
- interpretation
- confidence
- recommendation
- trading decision
"""

from enum import StrEnum


class SignalType(StrEnum):
    # Price
    PRICE_UP = "PRICE_UP"
    PRICE_DOWN = "PRICE_DOWN"
    PRICE_STABLE = "PRICE_STABLE"

    # Volume
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    VOLUME_STABLE = "VOLUME_STABLE"

    # Liquidity
    LIQUIDITY_UP = "LIQUIDITY_UP"
    LIQUIDITY_DOWN = "LIQUIDITY_DOWN"
    LIQUIDITY_STABLE = "LIQUIDITY_STABLE"

    # Market Cap
    MARKET_CAP_UP = "MARKET_CAP_UP"
    MARKET_CAP_DOWN = "MARKET_CAP_DOWN"
    MARKET_CAP_STABLE = "MARKET_CAP_STABLE"

    # FDV
    FDV_UP = "FDV_UP"
    FDV_DOWN = "FDV_DOWN"
    FDV_STABLE = "FDV_STABLE"