"""
Tests for DexSato Live Dashboard Entry Point.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from adaptive.dashboard.dashboard_card import (
    create_dashboard_card,
)

from presentation.live_dashboard import (
    build_output_file,
    extract_dashboard,
    generate_live_dashboard,
    normalize_token,
)


# ==========================================================
# Fixtures
# ==========================================================

def build_test_card():
    """
    Build a reusable DashboardCard.
    """

    return create_dashboard_card(

        token="BTC",

        decision="WATCH",

        confidence="HIGH",

        historical_success=66.67,

        seen_before=True,

        reasons=[
            "ACCUMULATION",
        ],

        summary="Live dashboard test.",

        last_updated=datetime.now(
            timezone.utc,
        ),

    )


# ==========================================================
# Token
# ==========================================================

def test_should_normalize_token():
    """
    Token symbols should be normalized.
    """

    assert normalize_token(
        " btc "
    ) == "BTC"


@pytest.mark.parametrize(
    "token",
    [
        "",
        "   ",
        "BTC/USD",
        "<BTC>",
    ],
)
def test_should_reject_invalid_token(
    token,
):
    """
    Unsupported token values should fail clearly.
    """

    with pytest.raises(
        ValueError,
    ):

        normalize_token(
            token,
        )


def test_should_build_token_output_file():
    """
    Output filename should use normalized token.
    """

    result = build_output_file(
        "BTC",
    )

    assert result.name == "btc_dashboard.html"


# ==========================================================
# Runner Result
# ==========================================================

def test_should_extract_dashboard_card():
    """
    Successful Runner results should expose DashboardCard.
    """

    card = build_test_card()

    result = extract_dashboard(
        {
            "success": True,
            "dashboard": card,
        }
    )

    assert result is card


def test_should_reject_failed_scan():
    """
    Failed scans should not generate dashboards.
    """

    with pytest.raises(
        RuntimeError,
        match="Market provider unavailable",
    ):

        extract_dashboard(
            {
                "success": False,
                "error": "Market provider unavailable",
            }
        )


def test_should_handle_first_scan_checkpoint():
    """
    First scans return no DashboardCard yet.
    """

    with pytest.raises(
        RuntimeError,
        match="Waiting for next scan",
    ):

        extract_dashboard(
            {
                "success": True,
                "message": (
                    "First market event recorded. "
                    "Waiting for next scan."
                ),
            }
        )


# ==========================================================
# Live Generation
# ==========================================================

@patch(
    "presentation.live_dashboard.write_live_dashboard"
)
@patch(
    "presentation.live_dashboard.run_scan"
)
def test_should_generate_dashboard_from_runner(
    mock_run_scan,
    mock_write_live_dashboard,
    tmp_path,
):
    """
    Live flow should use DashboardCard returned by Runner.
    """

    card = build_test_card()

    generated_file = (
        tmp_path
        / "btc_dashboard.html"
    ).resolve()

    mock_run_scan.return_value = {
        "success": True,
        "dashboard": card,
    }

    mock_write_live_dashboard.return_value = generated_file

    result = generate_live_dashboard(
        "btc",
    )

    assert result == generated_file

    mock_run_scan.assert_called_once_with(
        "BTC",
    )

    mock_write_live_dashboard.assert_called_once()

    call_arguments = (
        mock_write_live_dashboard.call_args.kwargs
    )

    assert call_arguments["card"] is card

    assert (
        call_arguments["output_file"].name
        == "btc_dashboard.html"
    )