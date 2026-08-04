"""
Tests for DexSato Dashboard HTML Presenter.
"""

from datetime import datetime, timezone

import pytest

from adaptive.dashboard.dashboard_card import (
    create_dashboard_card,
)

from presentation.dashboard_html_presenter import (
    build_dashboard_v2_css,
    format_dashboard_datetime,
    render_dashboard_components,
    render_dashboard_html,
)


# ==========================================================
# Fixture
# ==========================================================

def build_test_dashboard_card():
    """
    Build a complete reusable DashboardCard.
    """

    return create_dashboard_card(

        token="BTC",

        decision="WATCH",

        confidence="HIGH",

        historical_success=66.67,

        seen_before=True,

        reasons=[
            "ACCUMULATION",
            "STRONG_LIQUIDITY",
        ],

        summary="Bullish momentum detected.",

        last_updated=datetime(
            2026,
            7,
            22,
            10,
            30,
            tzinfo=timezone.utc,
        ),

    )


# ==========================================================
# Timestamp
# ==========================================================

def test_should_format_dashboard_datetime():
    """
    Presenter should retain timezone information.
    """

    result = format_dashboard_datetime(

        datetime(
            2026,
            7,
            22,
            10,
            30,
            tzinfo=timezone.utc,
        )

    )

    assert result == (
        "2026-07-22 10:30:00+00:00"
    )


def test_should_reject_invalid_dashboard_datetime():
    """
    Dashboard timestamps must use datetime objects.
    """

    with pytest.raises(
        ValueError,
        match="Dashboard timestamp must be a datetime",
    ):

        format_dashboard_datetime(
            "2026-07-22",
        )


# ==========================================================
# Component Orchestration
# ==========================================================

def test_should_render_dashboard_components():
    """
    Presenter should coordinate all approved components.
    """

    card = build_test_dashboard_card()

    html = render_dashboard_components(
        card,
    )

    assert "DexSato" in html

    assert "BTC" in html

    assert "Market Decision" in html

    assert "WATCH" in html

    assert "Radar Confidence" in html

    assert "HIGH" in html

    assert "Historical Intelligence" in html

    assert "66.67%" in html

    assert "KNOWN PATTERN" in html

    assert "Intelligence Summary" in html

    assert "Bullish momentum detected." in html

    assert "Evidence" in html

    assert "ACCUMULATION" in html

    assert "STRONG_LIQUIDITY" in html

    assert "dashboard-primary-grid" in html

    assert "dashboard-secondary-grid" in html


# ==========================================================
# Complete Dashboard
# ==========================================================

def test_should_render_dashboard_card_as_html():
    """
    Presenter should render a standalone Dashboard V2 page.
    """

    card = build_test_dashboard_card()

    html = render_dashboard_html(
        card,
    )

    assert "<!DOCTYPE html>" in html

    assert '<html lang="en">' in html

    assert "DexSato Dashboard" in html

    assert "BTC" in html

    assert "WATCH" in html

    assert "HIGH" in html

    assert "66.67%" in html

    assert "KNOWN PATTERN" in html

    assert "Bullish momentum detected." in html

    assert "ACCUMULATION" in html

    assert "STRONG_LIQUIDITY" in html

    assert (
        "2026-07-22 10:30:00+00:00"
        in html
    )

    assert "Engine:" in html

    assert "1.0.0" in html

    assert "dashboard-component-stack" in html

    assert "dashboard-footer" in html


# ==========================================================
# Safe HTML
# ==========================================================

def test_should_escape_dynamic_html_values():
    """
    Presenter and components must escape data-derived text.
    """

    card = create_dashboard_card(

        token="<script>alert('token')</script>",

        decision="<b>WATCH</b>",

        confidence="HIGH",

        historical_success=0.0,

        seen_before=False,

        reasons=[
            "<img src=x onerror=alert(1)>",
        ],

        summary="<script>alert('summary')</script>",

        last_updated=datetime.now(
            timezone.utc,
        ),

    )

    html = render_dashboard_html(
        card,
    )

    assert (
        "<script>alert('token')</script>"
        not in html
    )

    assert "&lt;script&gt;" in html

    assert (
        "<img src=x onerror=alert(1)>"
        not in html
    )

    assert (
        "&lt;img src=x onerror=alert(1)&gt;"
        in html
    )

    assert (
        "<script>alert('summary')</script>"
        not in html
    )


# ==========================================================
# Empty States
# ==========================================================

def test_should_render_empty_states():
    """
    Empty summary and reasons should use component states.
    """

    card = create_dashboard_card(

        token="ETH",

        decision="WATCH",

        confidence="MEDIUM",

        historical_success=0.0,

        seen_before=False,

        reasons=[],

        summary="   ",

        last_updated=datetime.now(
            timezone.utc,
        ),

    )

    html = render_dashboard_html(
        card,
    )

    assert (
        "No intelligence summary is currently available."
        in html
    )

    assert (
        "No supporting evidence available."
        in html
    )

    assert "NEW PATTERN" in html

    assert "MEDIUM" in html


# ==========================================================
# Theme
# ==========================================================

def test_should_build_dashboard_v2_css():
    """
    Dashboard V2 CSS should contain component layouts.
    """

    css = build_dashboard_v2_css()

    assert ".dashboard-primary-grid" in css

    assert ".dashboard-secondary-grid" in css

    assert ".decision-card-content" in css

    assert ".historical-panel-grid" in css

    assert ".evidence-list" in css

    assert "@media" in css


# ==========================================================
# Validation
# ==========================================================

def test_should_reject_invalid_dashboard_card():
    """
    Presenter requires the formal DashboardCard contract.
    """

    with pytest.raises(
        ValueError,
        match="DashboardCard is required",
    ):

        render_dashboard_html(
            None,
        )