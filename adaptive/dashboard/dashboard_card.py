"""
DexSato Dashboard Card

Dashboard Domain Artifact.

Responsibilities
----------------
- Represent a complete dashboard decision card
- Provide immutable dashboard contract

This module does NOT:
- perform calculations
- access repositories
- access databases
- make decisions
"""

from dataclasses import dataclass
from datetime import datetime, timezone


# --------------------------------------------------
# Metadata
# --------------------------------------------------

@dataclass(frozen=True)
class DashboardCardMetadata:
    """
    Dashboard metadata.
    """

    engine_version: str

    generated_at: datetime


# --------------------------------------------------
# Dashboard Card
# --------------------------------------------------

@dataclass(frozen=True)
class DashboardCard:
    """
    Complete dashboard decision card.
    """

    token: str

    decision: str

    confidence: str

    historical_success: float

    seen_before: bool

    reasons: list[str]

    summary: str

    last_updated: datetime

    metadata: DashboardCardMetadata


# --------------------------------------------------
# Factory
# --------------------------------------------------

def create_dashboard_card(
    *,
    token: str,
    decision: str,
    confidence: str,
    historical_success: float,
    seen_before: bool,
    reasons: list[str],
    summary: str,
    last_updated: datetime,
) -> DashboardCard:
    """
    Create immutable DashboardCard.
    """

    return DashboardCard(

        token=token,

        decision=decision,

        confidence=confidence,

        historical_success=historical_success,

        seen_before=seen_before,

        reasons=reasons,

        summary=summary,

        last_updated=last_updated,

        metadata=DashboardCardMetadata(

            engine_version="1.0.0",

            generated_at=datetime.now(
                timezone.utc,
            ),

        ),

    )