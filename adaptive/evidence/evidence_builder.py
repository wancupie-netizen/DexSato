"""
DexSato Evidence Builder

Build EvidenceArtifact from ExperienceArtifact.

Responsibilities
----------------
- Transform ExperienceArtifact into EvidenceArtifact

This module does NOT:
- access databases
- access repositories
- compile experience
- make recommendations
- perform AI analysis
"""

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
)

from adaptive.artifacts.evidence_artifact import (
    EvidenceArtifact,
    create_evidence,
)


# --------------------------------------------------
# Build
# --------------------------------------------------

def build_evidence(
    experience: ExperienceArtifact,
) -> EvidenceArtifact:
    """
    Build an EvidenceArtifact from an
    ExperienceArtifact.
    """

    return create_evidence(

        seen_before=experience.sample_size > 0,

        sample_size=experience.sample_size,

        success_rate=experience.success_rate,

        last_seen=experience.last_seen,

    )