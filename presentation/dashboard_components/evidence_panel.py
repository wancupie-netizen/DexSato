"""
DexSato Evidence Panel.

Displays the supporting evidence behind the current
DexSato decision.

Responsibilities
----------------
- Render decision evidence
- Escape user-visible text
- Use the shared Dashboard card container

This component does NOT:
- calculate evidence
- modify reasons
- access repositories
"""

from __future__ import annotations

from html import escape

from presentation.dashboard_components.card import (
    render_dashboard_card_container,
)


# ==========================================================
# Validation
# ==========================================================

def normalize_reasons(
    reasons: list[str],
) -> list[str]:
    """
    Validate and normalize dashboard reasons.
    """

    if not isinstance(
        reasons,
        list,
    ):

        raise ValueError(
            "Reasons must be a list."
        )

    normalized: list[str] = []

    for reason in reasons:

        if not isinstance(
            reason,
            str,
        ):

            raise ValueError(
                "Every reason must be a string."
            )

        value = reason.strip()

        if value:

            normalized.append(
                value,
            )

    return normalized


# ==========================================================
# Renderer
# ==========================================================

def render_evidence_panel(
    *,
    reasons: list[str],
) -> str:
    """
    Render Dashboard Evidence panel.
    """

    normalized = normalize_reasons(
        reasons,
    )

    if normalized:

        items = "".join(

            f"<li>{escape(reason)}</li>"

            for reason in normalized

        )

        content = (
            '<ul class="evidence-list">'
            f"{items}"
            "</ul>"
        )

    else:

        content = (
            '<p class="empty-state">'
            "No supporting evidence available."
            "</p>"
        )

    return render_dashboard_card_container(

        title="Evidence",

        subtitle=(
            "Signals supporting the current "
            "DexSato decision."
        ),

        content=content,

        css_class="evidence-panel",

    )