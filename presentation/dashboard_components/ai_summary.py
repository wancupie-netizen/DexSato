"""
DexSato AI Summary Component.

Displays the intelligence summary generated for the current
DashboardCard.

Responsibilities
----------------
- render intelligence summary
- escape user-visible text
- use shared Dashboard card

This component does NOT:
- generate AI
- access repositories
- modify summary
"""

from __future__ import annotations

from html import escape

from presentation.dashboard_components.card import (
    render_dashboard_card_container,
)


def normalize_summary(
    summary: str,
) -> str:
    """
    Normalize Dashboard summary.
    """

    if not isinstance(
        summary,
        str,
    ):

        raise ValueError(
            "Dashboard summary must be a string."
        )

    value = summary.strip()

    if not value:

        return (
            "No intelligence summary is currently "
            "available."
        )

    return value


def render_ai_summary_panel(
    *,
    summary: str,
) -> str:
    """
    Render Dashboard AI Summary panel.
    """

    normalized = normalize_summary(
        summary,
    )

    content = (
        '<p class="intelligence-summary">'
        f"{escape(normalized)}"
        "</p>"
    )

    return render_dashboard_card_container(

        title="Intelligence Summary",

        subtitle=(
            "DexSato explanation of the current "
            "market recommendation."
        ),

        content=content,

        css_class="summary-panel",

    )