"""
DexSato Dashboard Request Builder

Build DashboardRequest from
DecisionArtifact.

Responsibilities
----------------
- Build DashboardRequest
- Preserve Dashboard contract
- Isolate Runner from Dashboard

This module does NOT:
- access repositories
- access databases
- build dashboard cards
- perform business logic
"""

from __future__ import annotations

from datetime import datetime

from adaptive.dashboard.dashboard_request import (
    DashboardRequest,
    create_dashboard_request,
)

from core.artifacts.decision_artifact import (
    DecisionArtifact,
)


# --------------------------------------------------
# Builder
# --------------------------------------------------

def build_dashboard_request(
    *,
    token: str,
    decision: DecisionArtifact,
    knowledge_fingerprint: str,
    last_updated: datetime,
) -> DashboardRequest:
    """
    Build a DashboardRequest.

    Parameters
    ----------
    token
        Trading symbol.

    decision
        DecisionArtifact produced
        by Decision Engine.

    knowledge_fingerprint
        Stable Knowledge Fingerprint.

    last_updated
        Dashboard timestamp.

    Returns
    -------
    DashboardRequest
    """

    return create_dashboard_request(

        token=token,

        decision=decision,

        knowledge_fingerprint=
            knowledge_fingerprint,

        last_updated=
            last_updated,

    )