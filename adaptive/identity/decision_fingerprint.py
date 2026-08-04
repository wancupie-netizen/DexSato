"""
DexSato Adaptive Intelligence
Decision Fingerprint Generator

Responsibilities
----------------
Generate a deterministic fingerprint that uniquely represents
the cognitive state of a decision.

Properties
----------
- Deterministic
- Stateless
- Pure Function
- Zero External Dependencies
"""

from __future__ import annotations

import hashlib

from scanner.decision_types import DecisionType
from scanner.signal_types import SignalType
from scanner.interpretation_types import InterpretationType


def generate_decision_fingerprint(
    decision: DecisionType,
    observations: list[str],
    signals: list[SignalType],
    interpretations: list[InterpretationType],
) -> str:
    """
    Generate a deterministic decision fingerprint.

    Parameters
    ----------
    decision
        Decision produced by Decision Engine.

    observations
        Raw observations from Observation Builder.

    signals
        Atomic signals from Signal Detector.

    interpretations
        High-level interpretations from Interpretation Engine.

    Returns
    -------
    str
        SHA256 hexadecimal fingerprint.
    """

    payload = "|".join(
        [
            decision.value,
            *sorted(observations),
            *sorted(signal.value for signal in signals),
            *sorted(
                interpretation.value
                for interpretation in interpretations
            ),
        ]
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()