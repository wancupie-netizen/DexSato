"""
DexSato Decision Card Component.

Renders the primary market decision and confidence state
for Dashboard V2.

Responsibilities
----------------
- Render normalized decision text
- Render normalized confidence text
- Apply the official decision colour
- Use the shared Dashboard card container
- Escape all data-derived text

This component does NOT:
- make trading decisions
- calculate confidence
- access DashboardCard directly
- access repositories
- define global CSS
"""

from __future__ import annotations

from html import escape

from presentation.dashboard_components.card import (
    render_dashboard_card_container,
)

from presentation.dashboard_theme import (
    decision_colour,
)


# ==========================================================
# Supported Values
# ==========================================================

_SUPPORTED_DECISIONS = {
    "BUY",
    "WATCH",
    "SELL",
}

_SUPPORTED_CONFIDENCE = {
    "HIGH",
    "MEDIUM",
    "LOW",
}


# ==========================================================
# Normalization
# ==========================================================

def normalize_decision(
    decision: str,
) -> str:
    """
    Normalize a decision label.

    Unsupported decisions are represented as UNKNOWN.
    """

    if not isinstance(
        decision,
        str,
    ):

        raise ValueError(
            "Decision must be a string."
        )

    normalized = decision.strip().upper()

    if not normalized:

        raise ValueError(
            "Decision is required."
        )

    if normalized not in _SUPPORTED_DECISIONS:

        return "UNKNOWN"

    return normalized


def normalize_confidence(
    confidence: str,
) -> str:
    """
    Normalize a confidence label.

    Unsupported confidence values are represented as UNKNOWN.
    """

    if not isinstance(
        confidence,
        str,
    ):

        raise ValueError(
            "Confidence must be a string."
        )

    normalized = confidence.strip().upper()

    if not normalized:

        raise ValueError(
            "Confidence is required."
        )

    if normalized not in _SUPPORTED_CONFIDENCE:

        return "UNKNOWN"

    return normalized


# ==========================================================
# Decision Card
# ==========================================================

def render_decision_card(
    *,
    decision: str,
    confidence: str,
) -> str:
    """
    Render the primary DexSato Decision card.

    Parameters
    ----------
    decision
        Market decision such as BUY, WATCH, or SELL.

    confidence
        Decision confidence such as HIGH, MEDIUM, or LOW.

    Returns
    -------
    str
        Decision card HTML.
    """

    normalized_decision = normalize_decision(
        decision,
    )

    normalized_confidence = normalize_confidence(
        confidence,
    )

    colour = decision_colour(
        normalized_decision,
    )

    safe_decision = escape(
        normalized_decision,
    )

    safe_confidence = escape(
        normalized_confidence,
    )

    content = (
        '<div class="decision-card-content">'
        '<div class="decision-card-primary">'
        '<span class="decision-card-label">'
        "Current Decision"
        "</span>"
        '<strong class="decision-card-value" '
        f'style="color:{colour};">'
        f"{safe_decision}"
        "</strong>"
        "</div>"
        '<div class="decision-card-confidence">'
        '<span class="decision-card-label">'
        "Radar Confidence"
        "</span>"
        '<span class="badge confidence-badge">'
        f"{safe_confidence}"
        "</span>"
        "</div>"
        "</div>"
    )

    return render_dashboard_card_container(

        title="Market Decision",

        subtitle=(
            "Current DexSato recommendation "
            "and confidence classification."
        ),

        content=content,

        css_class="decision-panel",

    )