"""
Tests for DexSato Decision Card Component.
"""

import pytest

from presentation.dashboard_components.decision_card import (
    normalize_confidence,
    normalize_decision,
    render_decision_card,
)

from presentation.dashboard_theme import (
    THEME,
)


# ==========================================================
# Normalization
# ==========================================================

def test_should_normalize_decision():
    """
    Decision labels should be stripped and uppercased.
    """

    assert normalize_decision(
        " watch "
    ) == "WATCH"


def test_should_normalize_confidence():
    """
    Confidence labels should be stripped and uppercased.
    """

    assert normalize_confidence(
        " high "
    ) == "HIGH"


def test_should_convert_unsupported_values_to_unknown():
    """
    Unsupported presentation values should become UNKNOWN.
    """

    assert normalize_decision(
        "HOLD"
    ) == "UNKNOWN"

    assert normalize_confidence(
        "EXTREME"
    ) == "UNKNOWN"


# ==========================================================
# Decision Card
# ==========================================================

def test_should_render_watch_decision_card():
    """
    Decision component should render its official content.
    """

    html = render_decision_card(

        decision="WATCH",

        confidence="HIGH",

    )

    assert "Market Decision" in html

    assert "Current Decision" in html

    assert "WATCH" in html

    assert "Radar Confidence" in html

    assert "HIGH" in html

    assert "decision-panel" in html

    assert "decision-card-content" in html

    assert THEME["watch"] in html


@pytest.mark.parametrize(
    ("decision", "expected_colour"),
    [
        (
            "BUY",
            THEME["buy"],
        ),
        (
            "WATCH",
            THEME["watch"],
        ),
        (
            "SELL",
            THEME["sell"],
        ),
        (
            "UNKNOWN",
            THEME["unknown"],
        ),
    ],
)
def test_should_apply_official_decision_colour(
    decision,
    expected_colour,
):
    """
    Every decision should use the official Theme colour.
    """

    html = render_decision_card(

        decision=decision,

        confidence="MEDIUM",

    )

    assert expected_colour in html


# ==========================================================
# Validation
# ==========================================================

@pytest.mark.parametrize(
    "decision",
    [
        "",
        "   ",
    ],
)
def test_should_reject_empty_decision(
    decision,
):
    """
    Empty decisions should fail clearly.
    """

    with pytest.raises(
        ValueError,
        match="Decision is required",
    ):

        render_decision_card(

            decision=decision,

            confidence="HIGH",

        )


@pytest.mark.parametrize(
    "confidence",
    [
        "",
        "   ",
    ],
)
def test_should_reject_empty_confidence(
    confidence,
):
    """
    Empty confidence values should fail clearly.
    """

    with pytest.raises(
        ValueError,
        match="Confidence is required",
    ):

        render_decision_card(

            decision="WATCH",

            confidence=confidence,

        )


def test_should_reject_non_string_decision():
    """
    Decision contract requires a string.
    """

    with pytest.raises(
        ValueError,
        match="Decision must be a string",
    ):

        render_decision_card(

            decision=None,

            confidence="HIGH",

        )


def test_should_reject_non_string_confidence():
    """
    Confidence contract requires a string.
    """

    with pytest.raises(
        ValueError,
        match="Confidence must be a string",
    ):

        render_decision_card(

            decision="WATCH",

            confidence=None,

        )