"""
DexSato Historical Intelligence Panel.

Renders Adaptive History information currently available
inside DashboardCard.

Responsibilities
----------------
- Render historical success percentage
- Render seen-before status
- Render Adaptive Memory status
- Use the shared Dashboard card container
- Validate presentation values

This component does NOT:
- load historical experiences
- calculate history
- access repositories
- invent sample size
- access DashboardCard directly
- define global CSS
"""

from __future__ import annotations

from presentation.dashboard_components.card import (
    render_dashboard_card_container,
)


# ==========================================================
# Formatting
# ==========================================================

def format_historical_success(
    historical_success: float,
) -> str:
    """
    Format historical success as a percentage.

    Parameters
    ----------
    historical_success
        Historical success value between 0 and 100.

    Returns
    -------
    str
        Percentage formatted to two decimal places.
    """

    if not isinstance(
        historical_success,
        (int, float),
    ):

        raise ValueError(
            "Historical success must be numeric."
        )

    value = float(
        historical_success,
    )

    if not 0.0 <= value <= 100.0:

        raise ValueError(
            "Historical success must be between 0 and 100."
        )

    return f"{value:.2f}%"


def format_seen_before(
    seen_before: bool,
) -> str:
    """
    Convert seen-before state into a user-facing label.
    """

    if not isinstance(
        seen_before,
        bool,
    ):

        raise ValueError(
            "Seen-before status must be boolean."
        )

    return (
        "YES"
        if seen_before
        else "NO"
    )


def adaptive_memory_label(
    seen_before: bool,
) -> str:
    """
    Return the Adaptive Memory state.
    """

    if not isinstance(
        seen_before,
        bool,
    ):

        raise ValueError(
            "Seen-before status must be boolean."
        )

    return (
        "KNOWN PATTERN"
        if seen_before
        else "NEW PATTERN"
    )


# ==========================================================
# Historical Panel
# ==========================================================

def render_historical_panel(
    *,
    historical_success: float,
    seen_before: bool,
) -> str:
    """
    Render the DexSato Historical Intelligence panel.

    Parameters
    ----------
    historical_success
        Historical success percentage.

    seen_before
        Whether Adaptive History contains a matching pattern.

    Returns
    -------
    str
        Historical Intelligence panel HTML.
    """

    success_text = format_historical_success(
        historical_success,
    )

    seen_before_text = format_seen_before(
        seen_before,
    )

    memory_text = adaptive_memory_label(
        seen_before,
    )

    memory_class = (
        "adaptive-memory-known"
        if seen_before
        else "adaptive-memory-new"
    )

    content = (
        '<div class="historical-panel-grid">'

        '<div class="historical-metric">'
        '<span class="historical-metric-label">'
        "Historical Success"
        "</span>"
        '<strong class="historical-metric-value">'
        f"{success_text}"
        "</strong>"
        "</div>"

        '<div class="historical-metric">'
        '<span class="historical-metric-label">'
        "Seen Before"
        "</span>"
        '<strong class="historical-metric-value">'
        f"{seen_before_text}"
        "</strong>"
        "</div>"

        '<div class="historical-metric">'
        '<span class="historical-metric-label">'
        "Adaptive Memory"
        "</span>"
        f'<span class="badge {memory_class}">'
        f"{memory_text}"
        "</span>"
        "</div>"

        "</div>"
    )

    return render_dashboard_card_container(

        title="Historical Intelligence",

        subtitle=(
            "Adaptive memory derived from matching "
            "historical experience."
        ),

        content=content,

        css_class="historical-panel",

    )