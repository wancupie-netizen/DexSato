"""
Tests for DexSato Dashboard Theme.
"""

from presentation.dashboard_theme import (
    THEME,
    build_dashboard_css,
    decision_colour,
)


# ==========================================================
# Decision Colours
# ==========================================================

def test_should_return_watch_colour():
    """
    WATCH should use the official blue colour.
    """

    assert decision_colour(
        "WATCH",
    ) == THEME[
        "watch"
    ]


def test_should_return_buy_colour():
    """
    BUY should use the official green colour.
    """

    assert decision_colour(
        "BUY",
    ) == THEME[
        "buy"
    ]


def test_should_return_sell_colour():
    """
    SELL should use the official red colour.
    """

    assert decision_colour(
        "SELL",
    ) == THEME[
        "sell"
    ]


def test_should_normalize_decision_colour():
    """
    Decision labels should be stripped and normalized.
    """

    assert decision_colour(
        " watch ",
    ) == THEME[
        "watch"
    ]


def test_should_return_unknown_colour():
    """
    Unsupported decisions should use the neutral colour.
    """

    assert decision_colour(
        "HELLO",
    ) == THEME[
        "unknown"
    ]


def test_should_handle_non_string_decision():
    """
    Non-string values should safely use the neutral colour.
    """

    assert decision_colour(
        None,
    ) == THEME[
        "unknown"
    ]


# ==========================================================
# Theme Contract
# ==========================================================

def test_should_expose_required_theme_values():
    """
    Theme must provide all required Dashboard colours.
    """

    required_keys = {

        "background",

        "background_soft",

        "surface",

        "surface_alt",

        "surface_highlight",

        "text",

        "muted",

        "muted_soft",

        "border",

        "border_soft",

        "accent",

        "buy",

        "watch",

        "sell",

        "warning",

        "unknown",

    }

    assert required_keys.issubset(
        THEME.keys(),
    )


# ==========================================================
# CSS
# ==========================================================

def test_should_build_dashboard_css():
    """
    Shared CSS should contain the main Dashboard structures.
    """

    css = build_dashboard_css()

    assert "background" in css

    assert ".container" in css

    assert ".card" in css

    assert ".badge" in css

    assert ".card:hover" in css


def test_should_include_responsive_css():
    """
    Theme should support tablet and mobile layouts.
    """

    css = build_dashboard_css()

    assert "max-width: 820px" in css

    assert "max-width: 520px" in css


def test_should_include_accessibility_css():
    """
    Theme should respect reduced-motion preferences.
    """

    css = build_dashboard_css()

    assert (
        "prefers-reduced-motion"
        in css
    )

    assert "::selection" in css


def test_should_use_official_theme_values():
    """
    Generated CSS should use central Theme values.
    """

    css = build_dashboard_css()

    assert THEME[
        "background"
    ] in css

    assert THEME[
        "text"
    ] in css

    assert THEME[
        "accent"
    ] in css

    assert THEME[
        "border_soft"
    ] in css