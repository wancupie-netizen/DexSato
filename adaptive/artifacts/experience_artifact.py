"""
DexSato Experience Artifact

Immutable domain model representing accumulated
historical experience derived from one or more
LearningArtifacts.

Responsibilities
----------------
- Represent Experience
- Store Experience statistics
- Provide immutable Experience contract

This module does NOT:
- access databases
- compile learning
- build recommendations
- perform calculations
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


ENGINE_VERSION = "1.0.0"


# --------------------------------------------------
# Metadata
# --------------------------------------------------

@dataclass(frozen=True)
class ExperienceMetadata:
    """
    Metadata describing the ExperienceArtifact.
    """

    engine_version: str

    timestamp: datetime


# --------------------------------------------------
# Artifact
# --------------------------------------------------

@dataclass(frozen=True)
class ExperienceArtifact:
    """
    Immutable Experience Artifact.
    """

    experience_id: str

    fingerprint: str

    sample_size: int

    success_count: int

    failure_count: int

    success_rate: float

    last_seen: datetime

    metadata: ExperienceMetadata


# --------------------------------------------------
# Factory
# --------------------------------------------------

def create_experience(
    *,
    fingerprint: str,
    sample_size: int,
    success_count: int,
    failure_count: int,
    success_rate: float,
    last_seen: datetime,
) -> ExperienceArtifact:
    """
    Create an immutable ExperienceArtifact.
    """

    metadata = ExperienceMetadata(

        engine_version=ENGINE_VERSION,

        timestamp=datetime.now(
            timezone.utc,
        ),

    )

    return ExperienceArtifact(

        experience_id=f"EXP-{uuid4().hex[:12].upper()}",

        fingerprint=fingerprint,

        sample_size=sample_size,

        success_count=success_count,

        failure_count=failure_count,

        success_rate=success_rate,

        last_seen=last_seen,

        metadata=metadata,

    )