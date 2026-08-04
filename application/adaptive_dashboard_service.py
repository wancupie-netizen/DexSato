"""
DexSato Adaptive Dashboard Service

Application orchestration layer
for DashboardCard creation.

Responsibilities
----------------
- Load historical experiences
- Build HistorySummary
- Build DashboardCard

This module does NOT:
- build fingerprints
- build dashboard requests
- access databases directly
- perform calculations
- perform AI analysis
- make trading decisions
"""

from __future__ import annotations

from adaptive.dashboard.dashboard_builder import (
    build_dashboard_card,
)

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
)

from adaptive.dashboard.dashboard_request import (
    DashboardRequest,
)

from adaptive.history.history_builder import (
    build_history_summary,
)

from adaptive.history.history_repository import (
    find,
)


# --------------------------------------------------
# Adaptive Dashboard Service
# --------------------------------------------------

def build_adaptive_dashboard(
    request: DashboardRequest,
) -> DashboardCard:
    """
    Build a DashboardCard from
    a DashboardRequest.
    """

    # --------------------------------------------------
    # Load Experiences
    # --------------------------------------------------

    experiences = find(

        request.knowledge_fingerprint,

    )

    # --------------------------------------------------
    # Build History Summary
    # --------------------------------------------------

    history = build_history_summary(

        experiences,

    )

    # --------------------------------------------------
    # Decision Artifact
    # --------------------------------------------------

    decision = request.decision

    # --------------------------------------------------
    # Dashboard Card
    # --------------------------------------------------

    return build_dashboard_card(

        token=request.token,

        decision=decision.recommended_action,

        confidence=decision.confidence,

        summary=decision.summary,

        reasons=[

            reason.title

            for reason in decision.reasons

        ],

        history=history,

        last_updated=request.last_updated,

    )