"""
DexSato Knowledge Deserializer

Deserialize stored Knowledge payloads into
official KnowledgeArtifact objects.

Responsibilities
----------------
- Reconstruct KnowledgeMetadata
- Reconstruct KnowledgeArtifact

This module does NOT:
- perform market analysis
- perform aggregation
- build DTOs
- access databases
"""

from datetime import datetime

from core.artifacts.knowledge_artifact import (
    KnowledgeArtifact,
    KnowledgeMetadata,
)


# ==========================================================
# Deserialize
# ==========================================================

def deserialize_knowledge(
    payload: dict,
) -> KnowledgeArtifact:
    """
    Deserialize a Knowledge payload.

    Parameters
    ----------
    payload : dict

    Returns
    -------
    KnowledgeArtifact
    """

    metadata_data = payload["metadata"]

    metadata = KnowledgeMetadata(

        engine_version=
            metadata_data["engine_version"],

        timestamp=
            datetime.fromisoformat(
                metadata_data["timestamp"]
            ),

    )

    return KnowledgeArtifact(

        learning_artifact_id=
            payload["learning_artifact_id"],

        token=
            payload["token"],

        knowledge_fingerprint=
            payload["knowledge_fingerprint"],

        sample_size=
            payload["sample_size"],

        success_rate=
            float(
                payload["success_rate"]
            ),

        confidence=
            payload["confidence"],

        summary=
            payload["summary"],

        metadata=
            metadata,

        artifact_id=
            payload["knowledge_artifact_id"],

        created_at=
            datetime.fromisoformat(
                payload["created_at"]
            ),

    )