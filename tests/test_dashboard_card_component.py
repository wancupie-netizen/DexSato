"""
Tests for DexSato Shared Dashboard Card Component.
"""

import pytest

from presentation.dashboard_components.card import (
    render_dashboard_card_container,
)


# ==========================================================
# Standard Card
# ==========================================================

def test_should_render_dashboard_card_container():
    """
    Component should render the standard card structure.
    """

    html = render_dashboard_card_container(

        title="Historical Intelligence",

        subtitle="Adaptive memory from previous matches.",

        content=(
            '<p class="metric-value">66.67%</p>'
        ),

    )

    assert '<section class="card dashboard-panel">' in html

    assert "Historical Intelligence" in html

    assert (
        "Adaptive memory from previous matches."
        in html
    )

    assert '<p class="metric-value">66.67%</p>' in html

    assert "dashboard-panel-header" in html

    assert "dashboard-panel-content" in html


# ==========================================================
# Optional CSS Class
# ==========================================================

def test_should_add_component_css_class():
    """
    Component should support an additional CSS class.
    """

    html = render_dashboard_card_container(

        title="Decision",

        content="<p>WATCH</p>",

        css_class="decision-panel",

    )

    assert (
        'class="card dashboard-panel decision-panel"'
        in html
    )


# ==========================================================
# Safe Text
# ==========================================================

def test_should_escape_title_and_subtitle():
    """
    Text labels must be escaped before rendering.
    """

    html = render_dashboard_card_container(

        title="<script>Decision</script>",

        subtitle="<b>Unsafe subtitle</b>",

        content="<strong>WATCH</strong>",

    )

    assert "<script>Decision</script>" not in html

    assert (
        "&lt;script&gt;Decision&lt;/script&gt;"
        in html
    )

    assert "<b>Unsafe subtitle</b>" not in html

    assert (
        "&lt;b&gt;Unsafe subtitle&lt;/b&gt;"
        in html
    )

    # Internal component HTML remains intact.
    assert "<strong>WATCH</strong>" in html


# ==========================================================
# Optional Subtitle
# ==========================================================

def test_should_omit_empty_subtitle():
    """
    Empty subtitles should not create empty elements.
    """

    html = render_dashboard_card_container(

        title="Evidence",

        subtitle="   ",

        content="<p>Accumulation</p>",

    )

    assert "dashboard-panel-subtitle" not in html


# ==========================================================
# Validation
# ==========================================================

@pytest.mark.parametrize(
    "title",
    [
        "",
        "   ",
    ],
)
def test_should_reject_empty_title(
    title,
):
    """
    Every dashboard card must have a visible title.
    """

    with pytest.raises(
        ValueError,
        match="Dashboard card title is required",
    ):

        render_dashboard_card_container(

            title=title,

            content="<p>Content</p>",

        )


def test_should_reject_non_string_content():
    """
    Component content must be rendered HTML text.
    """

    with pytest.raises(
        ValueError,
        match="Dashboard card content must be a string",
    ):

        render_dashboard_card_container(

            title="Decision",

            content=None,

        )