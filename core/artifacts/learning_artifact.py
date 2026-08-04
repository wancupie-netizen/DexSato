"""
DexSato Learning Artifact

Official output produced by the Learning Engine.

Responsibilities
----------------
- Represent reusable learning extracted from an OutcomeArtifact.
- Preserve historical references.
- Provide immutable input for the Knowledge Store.

This module contains no business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from core.artifacts.outcome_artifact import OutcomeArtifact


# ==========================================================
# Learning Metadata
# ==========================================================

@dataclass(frozen=True, slots=True)
class LearningMetadata:
    """
    Technical metadata attached to a Learning Artifact.
    """

    engine_version: str

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ==========================================================
# Learning Artifact
# ==========================================================

@dataclass(frozen=True, slots=True)
class LearningArtifact:
    """
    Official output produced by the Learning Engine.

    Architecture Notes
    ------------------
    - Immutable
    - Deterministic
    - Explainable
    - Side-effect free

    Learning Engine never modifies the incoming OutcomeArtifact.
    """

    token: str

    outcome_artifact_id: str

    learning_status: str

    summary: str

    metadata: LearningMetadata

    artifact_id: str = field(
        default_factory=lambda: f"LRN-{uuid4().hex[:12].upper()}"
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    notes: Optional[str] = None

    @classmethod
    def from_outcome(
        cls,
        outcome: OutcomeArtifact,
        learning_status: str,
        summary: str,
        *,
        engine_version: str = "1.0.0",
        notes: Optional[str] = None,
    ) -> "LearningArtifact":
        """
        Convenience factory for creating a LearningArtifact
        from an existing OutcomeArtifact.
        """

        return cls(

            token=outcome.market_snapshot.symbol,

            outcome_artifact_id=outcome.artifact_id,

            learning_status=learning_status,

            summary=summary,

            metadata=LearningMetadata(
                engine_version=engine_version,
            ),

            notes=notes,
        )