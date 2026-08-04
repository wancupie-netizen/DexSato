"""
DexSato Learning Deserializer

Deserialize stored Learning payloads into
official LearningArtifact objects.

Responsibilities
----------------
- Reconstruct LearningMetadata
- Reconstruct LearningArtifact

This module does NOT:
- perform learning
- perform market analysis
- build DTOs
- access database
"""

from datetime import datetime

from core.artifacts.learning_artifact import (
    LearningArtifact,
    LearningMetadata,
)


# --------------------------------------------------
# Deserialize
# --------------------------------------------------

def deserialize_learning(
    payload: dict,
) -> LearningArtifact:
    """
    Deserialize a Learning payload.

    Parameters
    ----------
    payload : dict

    Returns
    -------
    LearningArtifact
    """

    metadata_data = payload["metadata"]

    metadata = LearningMetadata(

        engine_version=
            metadata_data["engine_version"],

        timestamp=
            datetime.fromisoformat(
                metadata_data["timestamp"]
            ),

    )

    return LearningArtifact(

        outcome_artifact_id=
            payload["outcome_artifact_id"],

        learning_status=
            payload["learning_status"],

        summary=
            payload["summary"],

        metadata=
            metadata,

        artifact_id=
            payload["learning_artifact_id"],

        created_at=
            datetime.fromisoformat(
                payload["created_at"]
            ),

        notes=
            payload.get("notes"),

    )