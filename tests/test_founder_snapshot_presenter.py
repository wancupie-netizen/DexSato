"""
Tests for AlphaRadar Snapshot Dashboard Presenter.
"""

import pytest

from presentation.founder_snapshot_presenter import (
    render_founder_snapshot_dashboard,
    render_snapshot_coin,
)


def build_snapshot():
    """
    Build one reusable snapshot payload.
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


def test_should_render_complete_snapshot_dashboard():
    """
    Dashboard should expose snapshot metadata and filters.
    """

    html = render_founder_snapshot_dashboard(
        build_snapshot(),
    )

    assert "<!DOCTYPE html>" in html

    assert "Top 100 Market Intelligence" in html

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