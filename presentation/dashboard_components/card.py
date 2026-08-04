"""
DexSato Shared Dashboard Card Component.

Provides the standard HTML container used by Dashboard V2
presentation components.

Responsibilities
----------------
- Render consistent dashboard card structure
- Render card title and optional subtitle
- Preserve trusted component HTML content
- Escape text-based labels safely

This component does NOT:
- calculate dashboard values
- access repositories
- access DashboardCard
- render complete pages
- define CSS
"""

from __future__ import annotations

from html import escape


# ==========================================================
# Shared Card
# ==========================================================

def render_dashboard_card_container(
    *,
    title: str,
    content: str,
    subtitle: str | None = None,
    css_class: str | None = None,
) -> str:
    """
    Render a reusable Dashboard card container.

    Parameters
    ----------
    title
        Human-readable card heading.

    content
        Trusted HTML produced by an internal presentation
        component.

    subtitle
        Optional descriptive text displayed below the title.

    css_class
        Optional additional CSS class for component-specific
        layout or presentation.

    Returns
    -------
    str
        Dashboard card HTML.
    """

    normalized_title = title.strip()

    if not normalized_title:

        raise ValueError(
            "Dashboard card title is required."
        )

    if not isinstance(
        content,
        str,
    ):

        raise ValueError(
            "Dashboard card content must be a string."
        )

    classes = [
        "card",
        "dashboard-panel",
    ]

    if css_class:

        normalized_css_class = css_class.strip()

        if normalized_css_class:

            classes.append(
                escape(
                    normalized_css_class,
                    quote=True,
                )
            )

    class_attribute = " ".join(
        classes,
    )

    subtitle_html = ""

    if subtitle is not None:

        normalized_subtitle = subtitle.strip()

        if normalized_subtitle:

            subtitle_html = (
                '<p class="dashboard-panel-subtitle">'
                f"{escape(normalized_subtitle)}"
                "</p>"
            )

    return (
        f'<section class="{class_attribute}">'
        '<header class="dashboard-panel-header">'
        '<h2 class="dashboard-panel-title">'
        f"{escape(normalized_title)}"
        "</h2>"
        f"{subtitle_html}"
        "</header>"
        '<div class="dashboard-panel-content">'
        f"{content}"
        "</div>"
        "</section>"
    )