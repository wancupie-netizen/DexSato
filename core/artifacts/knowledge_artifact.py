"""
DexSato Knowledge Artifact

Official output produced by the Knowledge Aggregator.

Responsibilities
----------------
- Represent reusable knowledge extracted from multiple
  LearningArtifacts.
- Preserve statistical evidence.
- Provide immutable input for Adaptive Intelligence.

This module contains no business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from core.artifacts.learning_artifact import LearningArtifact


# ==========================================================
# Knowledge Metadata
# ==========================================================

@dataclass(frozen=True, slots=True)
class KnowledgeMetadata:
    """
    Technical metadata attached to a Knowledge Artifact.
    """

    engine_version: str

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ==========================================================
# Knowledge Artifact
# ==========================================================

@dataclass(frozen=True, slots=True)
class KnowledgeArtifact:
    """
    Official output produced by the Knowledge Aggregator.

    Architecture Notes
    ------------------
    - Immutable
    - Deterministic
    - Explainable
    - Side-effect free

    Knowledge Aggregator never modifies the incoming
    LearningArtifacts.
    """

    learning_artifact_id: str

    token: str

    knowledge_fingerprint: str

    sample_size: int

    success_rate: float

    confidence: str

    summary: str

    metadata: KnowledgeMetadata

    artifact_id: str = field(
        default_factory=lambda: f"KNW-{uuid4().hex[:12].upper()}"
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def from_learning(
        cls,
        learning: LearningArtifact,
        *,
        knowledge_fingerprint: str,
        sample_size: int,
        success_rate: float,
        confidence: str,
        summary: str,
        engine_version: str = "1.0.0",
    ) -> "KnowledgeArtifact":
        """
        Convenience factory for creating a KnowledgeArtifact
        from an existing LearningArtifact.
        """

        return cls(

            learning_artifact_id=
                learning.artifact_id,

            token=
                learning.token,

            knowledge_fingerprint=
                knowledge_fingerprint,

            sample_size=
                sample_size,

            success_rate=
                success_rate,

            confidence=
                confidence,

            summary=
                summary,

            metadata=
                KnowledgeMetadata(
                    engine_version=engine_version,
                ),
        )