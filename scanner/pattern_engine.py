"""
DexSato Pattern Engine

Run every registered historical pattern detector.
"""

from scanner.patterns.persistent_watch import (
    detect as detect_persistent_watch,
)

from scanner.patterns.bullish_escalation import (
    detect as detect_bullish_escalation,
)

from scanner.patterns.bearish_deterioration import (
    detect as detect_bearish_deterioration,
)

from scanner.patterns.oscillation import (
    detect as detect_oscillation,
)


def detect_patterns(history):

    patterns = []

    patterns.extend(
        detect_persistent_watch(history)
    )

    patterns.extend(
        detect_bullish_escalation(history)
    )

    patterns.extend(
        detect_bearish_deterioration(history)
    )

    patterns.extend(
    detect_oscillation(history)
    )

    return patterns