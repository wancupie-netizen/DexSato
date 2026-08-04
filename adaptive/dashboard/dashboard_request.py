"""
DexSato Dashboard Request

Official input contract for the
Adaptive Dashboard Service.

Responsibilities
----------------
- Carry Dashboard input
- Isolate Runner from Dashboard
- Preserve domain boundaries

This module does NOT:
- perform calculations
- access repositories
- build dashboard cards
- contain business logic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from core.artifacts.decision_artifact import (
    DecisionArtifact,
)


# --------------------------------------------------
# Dashboard Request Metadata
# --------------------------------------------------

@dataclass(frozen=True, slots=True)
class DashboardRequestMetadata:
    """
    Metadata attached to a Dashboard Request.
    """

    engine_version: str

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc,
        )
    )


# --------------------------------------------------
# Dashboard Request
# --------------------------------------------------

@dataclass(frozen=True, slots=True)
class DashboardRequest:
    """
    Official contract between
    Runner and Adaptive Dashboard.

    Notes
    -----
    Immutable.

    Contains only the information
    required by the Dashboard layer.
    """

    token: str

    decision: DecisionArtifact

    knowledge_fingerprint: str

    last_updated: datetime

    metadata: DashboardRequestMetadata

    request_id: str = field(
        default_factory=lambda:
            f"DBR-{uuid4().hex[:12].upper()}"
    )


# --------------------------------------------------
# Factory
# --------------------------------------------------

def create_dashboard_request(
    *,
    token: str,
    decision: DecisionArtifact,
    knowledge_fingerprint: str,
    last_updated: datetime,
    engine_version: str = "1.0.0",
) -> DashboardRequest:
    """
    Create a DashboardRequest.
    """

    return DashboardRequest(

        token=token,

        decision=decision,

        knowledge_fingerprint=knowledge_fingerprint,

        last_updated=last_updated,

        metadata=DashboardRequestMetadata(

            engine_version=engine_version,

        ),

    )