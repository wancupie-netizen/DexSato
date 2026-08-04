"""
DexSato Evidence Artifact

Immutable domain model representing evidence
derived from historical Experience.

Responsibilities
----------------
- Represent dashboard evidence
- Provide immutable Evidence contract

This module does NOT:
- access databases
- compile experience
- calculate statistics
- make recommendations
"""

from dataclasses import dataclass
from datetime import datetime, timezone


ENGINE_VERSION = "1.0.0"


# --------------------------------------------------
# Metadata
# --------------------------------------------------

@dataclass(frozen=True)
class EvidenceMetadata:
    """
    Metadata describing the EvidenceArtifact.
    """

    engine_version: str

    timestamp: datetime


# --------------------------------------------------
# Artifact
# --------------------------------------------------

@dataclass(frozen=True)
class EvidenceArtifact:
    """
    Immutable Evidence Artifact.
    """

    seen_before: bool

    sample_size: int

    success_rate: float

    last_seen: datetime | None

    metadata: EvidenceMetadata


# --------------------------------------------------
# Factory
# --------------------------------------------------

def create_evidence(
    *,
    seen_before: bool,
    sample_size: int,
    success_rate: float,
    last_seen: datetime | None,
) -> EvidenceArtifact:
    """
    Create an immutable EvidenceArtifact.
    """

    metadata = EvidenceMetadata(

        engine_version=ENGINE_VERSION,

        timestamp=datetime.now(
            timezone.utc,
        ),

    )

    return EvidenceArtifact(

        seen_before=seen_before,

        sample_size=sample_size,

        success_rate=success_rate,

        last_seen=last_seen,

        metadata=metadata,

    )