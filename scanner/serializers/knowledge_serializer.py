"""
DexSato Knowledge Serializer

Serialize KnowledgeArtifact into a database payload.

Responsibilities
----------------
- Convert KnowledgeArtifact into dict.
- Produce payload compatible with knowledge_events.
- Contain no business logic.

This module does NOT:
- access databases
- deserialize objects
- evaluate knowledge
"""

from core.artifacts.knowledge_artifact import (
    KnowledgeArtifact,
)


# ==========================================================
# Serializer
# ==========================================================

def serialize_knowledge(
    artifact: KnowledgeArtifact,
) -> dict:
    """
    Serialize a KnowledgeArtifact.

    Parameters
    ----------
    artifact : KnowledgeArtifact

    Returns
    -------
    dict
    """

    return {

        "token":
            artifact.token,

        "learning_artifact_id":
            artifact.learning_artifact_id,

        "knowledge_artifact_id":
            artifact.artifact_id,

        "knowledge_fingerprint":
            artifact.knowledge_fingerprint,

        "sample_size":
            artifact.sample_size,

        "success_rate":
            artifact.success_rate,

        "confidence":
            artifact.confidence,

        "summary":
            artifact.summary,

        "metadata": {

            "engine_version":
                artifact.metadata.engine_version,

            "timestamp":
                artifact.metadata.timestamp.isoformat(),

        },

        "created_at":
            artifact.created_at.isoformat(),

    }