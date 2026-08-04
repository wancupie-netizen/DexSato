"""
DexSato Dashboard Collection Service

Application orchestration layer for building
multiple DashboardCard artifacts.

Responsibilities
----------------
- Receive DashboardRequest collection
- Build one DashboardCard for each request
- Preserve request ordering
- Return DashboardCard collection

This module does NOT:
- build DashboardRequest objects
- access databases directly
- access repositories directly
- calculate historical statistics
- perform AI analysis
- make trading decisions
"""

from __future__ import annotations

from collections.abc import Iterable

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
)

from adaptive.dashboard.dashboard_request import (
    DashboardRequest,
)

from application.adaptive_dashboard_service import (
    build_adaptive_dashboard,
)


# ==========================================================
# Dashboard Collection
# ==========================================================

def build_dashboard_collection(
    *,
    requests: Iterable[DashboardRequest],
) -> list[DashboardCard]:
    """
    Build a DashboardCard collection.

    Parameters
    ----------
    requests
        DashboardRequest objects to process.

    Returns
    -------
    list[DashboardCard]
        Dashboard cards in the same order
        as the supplied requests.
    """

    cards: list[DashboardCard] = []

    for request in requests:

        card = build_adaptive_dashboard(
            request,
        )

        cards.append(
            card,
        )

    return cards