"""
DexSato Learning Engine

Transform OutcomeArtifact into a reusable
LearningArtifact.

Responsibilities
----------------
- Consume OutcomeArtifact
- Produce LearningArtifact
- Preserve historical references

Learning Engine does NOT

- modify OutcomeArtifact
- modify DecisionArtifact
- access databases
- access external APIs
- update Knowledge Store
"""

from core.artifacts.learning_artifact import LearningArtifact
from core.artifacts.outcome_artifact import OutcomeArtifact


ENGINE_VERSION = "1.0.0"


def build_learning(
    outcome: OutcomeArtifact,
) -> LearningArtifact:
    """
    Build a LearningArtifact from an OutcomeArtifact.

    Parameters
    ----------
    outcome
        Completed OutcomeArtifact.

    Returns
    -------
    LearningArtifact
    """

    if outcome is None:

        raise ValueError(
            "OutcomeArtifact is required."
        )

    # ------------------------------------------------------
    # Learning Classification
    # ------------------------------------------------------

    snapshot_status = outcome.snapshot_status.upper()

    if snapshot_status == "RECORDED":

        learning_status = "CONFIRMED"

        summary = (
            "Outcome recorded successfully."
        )

    else:

        learning_status = "UNKNOWN"

        summary = (
            "Outcome could not be classified."
        )

    # ------------------------------------------------------
    # Build Learning Artifact
    # ------------------------------------------------------

    return LearningArtifact.from_outcome(

        outcome=outcome,

        learning_status=learning_status,

        summary=summary,

        engine_version=ENGINE_VERSION,

    )