"""
Tests for DexSato Historical Intelligence Panel.
"""

import pytest

from presentation.dashboard_components.historical_panel import (
    adaptive_memory_label,
    format_historical_success,
    format_seen_before,
    render_historical_panel,
)


# ==========================================================
# Historical Success
# ==========================================================

def test_should_format_historical_success():
    """
    Historical success should use two decimal places.
    """

    assert format_historical_success(
        66.67
    ) == "66.67%"

    assert format_historical_success(
        0
    ) == "0.00%"

    assert format_historical_success(
        100
    ) == "100.00%"


@pytest.mark.parametrize(
    "value",
    [
        -0.01,
        100.01,
    ],
)
def test_should_reject_out_of_range_success(
    value,
):
    """
    Percentages outside zero to one hundred are invalid.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Historical success must be between "
            "0 and 100"
        ),
    ):

        format_historical_success(
            value,
        )


def test_should_reject_non_numeric_success():
    """
    Historical success must be numeric.
    """

    with pytest.raises(
        ValueError,
        match="Historical success must be numeric",
    ):

        format_historical_success(
            "66.67",
        )


# ==========================================================
# Seen-Before Status
# ==========================================================

def test_should_format_seen_before_status():
    """
    Boolean history state should use explicit labels.
    """

    assert format_seen_before(
        True
    ) == "YES"

    assert format_seen_before(
        False
    ) == "NO"


def test_should_build_adaptive_memory_label():
    """
    Adaptive Memory should distinguish known and new patterns.
    """

    assert adaptive_memory_label(
        True
    ) == "KNOWN PATTERN"

    assert adaptive_memory_label(
        False
    ) == "NEW PATTERN"


@pytest.mark.parametrize(
    "value",
    [
        1,
        0,
        "True",
        None,
    ],
)
def test_should_reject_non_boolean_seen_before(
    value,
):
    """
    Seen-before state must use a real boolean.
    """

    with pytest.raises(
        ValueError,
        match="Seen-before status must be boolean",
    ):

        format_seen_before(
            value,
        )


# ==========================================================
# Historical Panel
# ==========================================================

def test_should_render_known_historical_pattern():
    """
    Known patterns should display active Adaptive Memory.
    """

    html = render_historical_panel(

        historical_success=66.67,

        seen_before=True,

    )

    assert "Historical Intelligence" in html

    assert "Historical Success" in html

    assert "66.67%" in html

    assert "Seen Before" in html

    assert "YES" in html

    assert "Adaptive Memory" in html

    assert "KNOWN PATTERN" in html

    assert "adaptive-memory-known" in html

    assert "historical-panel" in html


def test_should_render_new_historical_pattern():
    """
    New patterns should display an empty-history state.
    """

    html = render_historical_panel(

        historical_success=0.0,

        seen_before=False,

    )

    assert "0.00%" in html

    assert "NO" in html

    assert "NEW PATTERN" in html

    assert "adaptive-memory-new" in html


def test_should_not_render_unsupported_sample_size():
    """
    Panel must not invent sample size that is absent
    from the DashboardCard contract.
    """

    html = render_historical_panel(

        historical_success=66.67,

        seen_before=True,

    )

    assert "Sample Size" not in html

    assert "observations" not in html