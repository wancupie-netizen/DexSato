"""
DexSato Dashboard Builder

Build DashboardCard from Decision + HistorySummary.

Responsibilities
----------------
- Build DashboardCard
- Combine Core + Historical Intelligence

This module does NOT:
- access repositories
- access databases
- perform AI analysis
"""

from datetime import datetime

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
    create_dashboard_card,
)

from adaptive.history.history_summary import (
    HistorySummary,
)


# --------------------------------------------------
# Build
# --------------------------------------------------

def build_dashboard_card(
    *,
    token: str,
    decision: str,
    confidence: str,
    summary: str,
    reasons: list[str],
    history: HistorySummary,
    last_updated: datetime,
) -> DashboardCard:
    """
    Build DashboardCard.
    """

    return create_dashboard_card(

        token=token,

        decision=decision,

        confidence=confidence,

        historical_success=history.success_rate,

        seen_before=history.seen_before,

        reasons=reasons,

        summary=summary,

        last_updated=last_updated,

    )