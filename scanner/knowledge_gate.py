"""
DexSato Knowledge Gate

Decide whether an Intelligence Package deserves
to become persistent knowledge.

Responsibilities
----------------
- Compare current and previous Intelligence Packages
- Detect meaningful intelligence changes
- Decide whether to store knowledge

This module does NOT:
- access databases
- save data
- publish feeds
- generate fingerprints
"""

from core.artifacts.decision_artifact import DecisionArtifact


def _normalize_interpretations(package: dict) -> set[str]:
    """
    Normalize interpretations into a comparable set.
    """

    return {
        item.value if hasattr(item, "value") else str(item)
        for item in package.get("interpretations", [])
    }


def _decision_value(decision) -> str | None:
    """
    Return comparable decision value.

    Supports:
    - DecisionArtifact (new)
    - legacy dict (backward compatibility)
    """

    if decision is None:
        return None

    if isinstance(decision, DecisionArtifact):
        return decision.recommended_action

    if isinstance(decision, dict):
        return decision.get("decision")

    return None


def should_store(
    current: dict,
    previous: dict | None,
) -> bool:
    """
    Decide whether the current Intelligence Package
    should be stored.
    """

    # ---------------------------------------
    # First Knowledge
    # ---------------------------------------

    if previous is None:
        return True

    # ---------------------------------------
    # Decision Changed
    # ---------------------------------------

    current_decision = _decision_value(
        current.get("decision")
    )

    previous_decision = _decision_value(
        previous.get("decision")
    )

    if current_decision != previous_decision:
        return True

    # ---------------------------------------
    # Interpretation Changed
    # ---------------------------------------

    if (
        _normalize_interpretations(current)
        !=
        _normalize_interpretations(previous)
    ):
        return True

    # ---------------------------------------
    # No Meaningful Change
    # ---------------------------------------

    return False