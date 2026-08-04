"""
DexSato Knowledge Fingerprint

Build stable Knowledge fingerprints from
LearningArtifacts.

Responsibilities
----------------
- Produce deterministic fingerprints
- Normalize ordering
- Contain no business logic beyond
  fingerprint construction

This module does NOT:
- access databases
- calculate statistics
- assign confidence
"""

from core.artifacts.learning_artifact import (
    LearningArtifact,
)


def build_fingerprint(
    learnings: list[LearningArtifact],
) -> str:
    """
    Build a deterministic fingerprint.

    Parameters
    ----------
    learnings

    Returns
    -------
    str
    """

    if not learnings:

        raise ValueError(
            "At least one LearningArtifact is required."
        )

    latest = learnings[-1]

    #
    # Placeholder.
    #
    # Future versions will derive the
    # fingerprint from:
    #
    # - decision
    # - interpretations
    # - signal groups
    #
    # For now we use the learning status.
    #

    return latest.learning_status.upper()