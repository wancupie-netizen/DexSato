"""
DexSato Dashboard Service

Application orchestration layer
for DashboardContext creation.

Responsibilities
----------------
- Convert ExperienceArtifact into EvidenceArtifact
- Convert EvidenceArtifact into DashboardContext

This module does NOT:
- access databases
- access repositories
- compile experience
- make trading decisions
"""

from datetime import datetime

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
)

from adaptive.dashboard.dashboard_adapter import (
    build_dashboard_context,
)

from adaptive.dashboard.dashboard_context import (
    DashboardContext,
    create_dashboard_context,
)

from adaptive.evidence.evidence_builder import (
    build_evidence,
)


# --------------------------------------------------
# Dashboard Service
# --------------------------------------------------

def build_dashboard(
    *,
    token: str,
    decision: str,
    confidence: str,
    summary: str,
    reasons: list[str],
    experience: ExperienceArtifact,
    updated_at: datetime,
) -> DashboardContext:
    """
    Build DashboardContext
    from Core Decision + Adaptive Experience.
    """

    evidence = build_evidence(
        experience,
    )

    return create_dashboard_context(

        token=token,

        decision=decision,

        confidence=confidence,

        summary=summary,

        reasons=reasons,

        evidence=evidence,

        updated_at=updated_at,

    )