"""
Tests for AlphaRadar V1 Snapshot Dashboard Presenter.
"""

import pytest

from presentation.founder_snapshot_presenter import (
    confidence_class,
    decision_class,
    render_founder_snapshot_dashboard,
    render_snapshot_coin,
)


def build_snapshot():
    """
    Build one reusable V1 snapshot payload.
    """

    return {
        "generated_at": (
            "2026-07-24T08:00:00+00:00"
        ),
        "total_coins": 2,
        "available_coins": 1,
        "unavailable_coins": 1,
        "coins": [
            {
                "token": "BTC",
                "available": True,
                "decision": "WATCH",
                "confidence": "HIGH",
                "historical_success": 66.67,
                "seen_before": True,
                "reasons": [
                    "MOMENTUM",
                ],
                "summary": (
                    "Market intelligence available."
                ),
                "error": None,
            },
            {
                "token": "TEST",
                "available": False,
                "decision": None,
                "confidence": None,
                "historical_success": None,
                "seen_before": False,
                "reasons": [],
                "summary": None,
                "error": "Unsupported market.",
            },
        ],
    }


# ==========================================================
# Confidence Classes
# ==========================================================

def test_should_map_confidence_classes():
    """
    Confidence levels should use official visual classes.
    """

    assert confidence_class(
        "HIGH",
    ) == "confidence-high"

    assert confidence_class(
        "MEDIUM",
    ) == "confidence-medium"

    assert confidence_class(
        "LOW",
    ) == "confidence-low"

    assert confidence_class(
        "UNKNOWN",
    ) == "confidence-unknown"


# ==========================================================
# Decision Classes
# ==========================================================

def test_should_map_decision_classes():
    """
    Decisions should use official visual classes.
    """

    assert decision_class(
        "BUY",
    ) == "decision-buy"

    assert decision_class(
        "WATCH",
    ) == "decision-watch"

    assert decision_class(
        "REVIEW",
    ) == "decision-review"

    assert decision_class(
        "SELL",
    ) == "decision-sell"

    assert decision_class(
        "IGNORE",
    ) == "decision-ignore"

    assert decision_class(
        "UNAVAILABLE",
    ) == "decision-unavailable"

    assert decision_class(
        "UNKNOWN",
    ) == "decision-unknown"


# ==========================================================
# Coin Rendering
# ==========================================================

def test_should_render_available_snapshot_coin():
    """
    Available coin data should render correctly.
    """

    html = render_snapshot_coin(
        build_snapshot()["coins"][0],
    )

    assert "BTC" in html

    assert "WATCH" in html

    assert "HIGH" in html

    assert "66.67%" in html

    assert "KNOWN PATTERN" in html

    assert "MOMENTUM" in html

    assert "decision-watch" in html

    assert "confidence-high" in html

    assert "decision-badge" in html

    assert "confidence-badge" in html


def test_should_render_medium_confidence_colour():
    """
    Medium confidence should use the amber class.
    """

    coin = build_snapshot()["coins"][0].copy()

    coin["confidence"] = "MEDIUM"

    html = render_snapshot_coin(
        coin,
    )

    assert "confidence-medium" in html


def test_should_render_low_confidence_colour():
    """
    Low confidence should use the red class.
    """

    coin = build_snapshot()["coins"][0].copy()

    coin["confidence"] = "LOW"

    html = render_snapshot_coin(
        coin,
    )

    assert "confidence-low" in html


def test_should_render_unavailable_snapshot_coin():
    """
    Unavailable coin should remain visible.
    """

    html = render_snapshot_coin(
        build_snapshot()["coins"][1],
    )

    assert "TEST" in html

    assert "UNAVAILABLE" in html

    assert "Unsupported market." in html

    assert "decision-unavailable" in html


# ==========================================================
# Full Dashboard
# ==========================================================

def test_should_render_complete_snapshot_dashboard():
    """
    Dashboard should expose V1 metadata and filters.
    """

    html = render_founder_snapshot_dashboard(
        build_snapshot(),
    )

    assert "<!DOCTYPE html>" in html

    assert (
        "AlphaRadar Market Intelligence"
        in html
    )

    assert (
        "Current V1 production market universe."
        in html
    )

    assert "Total Markets" in html

    assert "Available" in html

    assert "Unavailable" in html

    assert "BTC" in html

    assert "TEST" in html

    assert 'id="token-search"' in html

    assert 'id="decision-filter"' in html

    assert (
        "2026-07-24T08:00:00+00:00"
        in html
    )


def test_should_render_live_dashboard_elements():
    """
    Dashboard should visibly communicate that it is active.
    """

    html = render_founder_snapshot_dashboard(
        build_snapshot(),
    )

    assert "System Live" in html

    assert "Snapshot Online" in html

    assert "Next Planned Scan" in html

    assert "radar-wrap" in html

    assert "radar-sweep" in html

    assert "live-dot" in html

    assert 'id="snapshot-age"' in html

    assert 'id="next-scan-time"' in html

    assert (
        'id="next-scan-countdown"'
        in html
    )

    assert (
        "08:00, 14:00 and 20:00 MYT"
        in html
    )


def test_should_render_founder_footer():
    """
    Dashboard should preserve the founder dedication.
    """

    html = render_founder_snapshot_dashboard(
        build_snapshot(),
    )

    assert "Made for Sya ❤️" in html

    assert "Snapshot generated:" in html


def test_should_keep_search_and_filter_script():
    """
    Existing client-side controls should remain functional.
    """

    html = render_founder_snapshot_dashboard(
        build_snapshot(),
    )

    assert "function applyFilters()" in html

    assert (
        'searchInput.addEventListener('
        in html
    )

    assert (
        'decisionFilter.addEventListener('
        in html
    )


def test_should_render_snapshot_freshness_script():
    """
    Snapshot age and next scan should update in browser.
    """

    html = render_founder_snapshot_dashboard(
        build_snapshot(),
    )

    assert "function updateSnapshotAge()" in html

    assert "function nextPlannedScan(" in html

    assert "function updateNextScan()" in html

    assert (
        '"Asia/Kuala_Lumpur"'
        in html
    )

    assert "window.setInterval(" in html


# ==========================================================
# Security and Validation
# ==========================================================

def test_should_escape_snapshot_values():
    """
    Snapshot-derived values must be escaped.
    """

    coin = {
        "token": "<BTC>",
        "available": False,
        "error": "<script>alert(1)</script>",
    }

    html = render_snapshot_coin(
        coin,
    )

    assert "<BTC>" not in html

    assert "&lt;BTC&gt;" in html

    assert "<script>" not in html

    assert "&lt;script&gt;" in html


def test_should_reject_invalid_snapshot():
    """
    Presenter requires a valid snapshot dictionary.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Founder snapshot must be a dictionary"
        ),
    ):

        render_founder_snapshot_dashboard(
            None,
        )


def test_should_reject_invalid_coin_collection():
    """
    Snapshot coin data must be a list.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Founder snapshot coin data must be a list"
        ),
    ):

        render_founder_snapshot_dashboard(
            {
                "coins": None,
            },
        )