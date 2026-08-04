"""
DexSato Knowledge Fingerprint

Build a stable fingerprint from an Intelligence Package.

Responsibilities
----------------
- Generate deterministic fingerprints
- Normalize interpretation ordering

This module does NOT:
- access databases
- decide whether knowledge should be stored
- save data
"""

import hashlib

from core.artifacts.decision_artifact import DecisionArtifact


def _decision_value(decision) -> str:
    """
    Return a normalized decision value.

    Supports:
    - DecisionArtifact
    - Legacy dict
    """

    if isinstance(decision, DecisionArtifact):
        return decision.recommended_action

    if isinstance(decision, dict):
        return decision.get("decision", "")

    return str(decision)


def build_knowledge_fingerprint(package: dict) -> str:
    """
    Build a stable Knowledge Fingerprint.

    Parameters
    ----------
    package : dict

    Returns
    -------
    str
        SHA-256 fingerprint.
    """

    decision = _decision_value(
        package["decision"]
    )

    interpretations = sorted(
        interpretation.value
        if hasattr(interpretation, "value")
        else str(interpretation)
        for interpretation in package["interpretations"]
    )

    fingerprint_source = "|".join(
        [
            decision,
            *interpretations,
        ]
    )

    return hashlib.sha256(
        fingerprint_source.encode("utf-8")
    ).hexdigest()