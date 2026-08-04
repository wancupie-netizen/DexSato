"""
DexSato Signal Detector

Convert normalized market observations into atomic signals.

This module is responsible only for signal detection.

It does NOT:
- interpret signals
- assign confidence
- generate recommendations
- make trading decisions
"""

from scanner.signal_types import SignalType


SIGNAL_MAPPING = {
    "price_change_pct": "PRICE",
    "volume_change_pct": "VOLUME",
    "liquidity_change_pct": "LIQUIDITY",
    "market_cap_change_pct": "MARKET_CAP",
    "fdv_change_pct": "FDV",
}


def detect_signals(observation) -> set[SignalType]:
    """
    Convert a normalized observation into atomic signals.

    Parameters
    ----------
    observation : dict

    Returns
    -------
    set[SignalType]
    """

    signals: set[SignalType] = set()

    for field, prefix in SIGNAL_MAPPING.items():

        value = observation.get(field)

        if value is None:
            continue

        if value > 0:
            signal_name = f"{prefix}_UP"

        elif value < 0:
            signal_name = f"{prefix}_DOWN"

        else:
            signal_name = f"{prefix}_STABLE"

        signals.add(SignalType[signal_name])

    return signals