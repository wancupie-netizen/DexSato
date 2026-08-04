"""
DexSato Dashboard Adapter

Build DashboardContext from Core Decision
and Adaptive Evidence.

Responsibilities
----------------
- Combine Core Decision data
- Combine Adaptive Evidence
- Produce DashboardContext

This module does NOT:
- access databases
- access repositories
- compile experience
- build evidence
- make trading decisions
"""

from datetime import datetime

from adaptive.artifacts.evidence_artifact import (
    EvidenceArtifact,
)

from adaptive.dashboard.dashboard_context import (
    DashboardContext,
    create_dashboard_context,
)


# --------------------------------------------------
# Build Dashboard Context
# --------------------------------------------------

def build_dashboard_context(
    *,
    token: str,
    decision: str,
    confidence: str,
    summary: str,
    reasons: list[str],
    evidence: EvidenceArtifact,
    updated_at: datetime,
) -> DashboardContext:
    """
    Build DashboardContext for presentation.
    """

    return create_dashboard_context(

        token=token,

        decision=decision,

        confidence=confidence,

        summary=summary,

        reasons=reasons,

        evidence=evidence,

        updated_at=updated_at,

    )