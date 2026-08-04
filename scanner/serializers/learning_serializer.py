"""
DexSato Learning Serializer

Serialize LearningArtifact into a database payload.

Responsibilities
----------------
- Convert LearningArtifact into dict.
- Produce payload compatible with learning_events.
- Contain no business logic.

This module does NOT:
- access databases
- deserialize objects
- evaluate learning
"""

from core.artifacts.learning_artifact import (
    LearningArtifact,
)


# ==========================================================
# Serializer
# ==========================================================

def serialize_learning(
    artifact: LearningArtifact,
) -> dict:
    """
    Serialize a LearningArtifact.

    Parameters
    ----------
    artifact : LearningArtifact

    Returns
    -------
    dict
    """

    return {

        "token":
            artifact.token,

        "outcome_artifact_id":
            artifact.outcome_artifact_id,

        "learning_artifact_id":
            artifact.artifact_id,

        "learning_status":
            artifact.learning_status,

        "summary":
            artifact.summary,

        "metadata": {

            "engine_version":
                artifact.metadata.engine_version,

            "timestamp":
                artifact.metadata.timestamp.isoformat(),

        },

        "notes":
            artifact.notes,

        "created_at":
            artifact.created_at.isoformat(),

    }