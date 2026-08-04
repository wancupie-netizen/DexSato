"""
DexSato Dashboard Context

View model exposed to Dashboard.

Responsibilities
----------------
- Represent Dashboard data
- Aggregate Core Decision and Adaptive Evidence
- Provide immutable Dashboard contract

This module does NOT:
- access databases
- access repositories
- build evidence
- compile experience
- make decisions
"""

from dataclasses import dataclass
from datetime import datetime

from adaptive.artifacts.evidence_artifact import (
    EvidenceArtifact,
)


# --------------------------------------------------
# Dashboard Context
# --------------------------------------------------

@dataclass(frozen=True)
class DashboardContext:
    """
    Immutable Dashboard Context.

    This object is the only Adaptive object
    consumed by the Dashboard layer.
    """

    token: str

    decision: str

    confidence: str

    summary: str

    reasons: list[str]

    evidence: EvidenceArtifact

    updated_at: datetime


# --------------------------------------------------
# Factory
# --------------------------------------------------

def create_dashboard_context(
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
    Create an immutable DashboardContext.
    """

    return DashboardContext(

        token=token,

        decision=decision,

        confidence=confidence,

        summary=summary,

        reasons=list(reasons),

        evidence=evidence,

        updated_at=updated_at,

    )