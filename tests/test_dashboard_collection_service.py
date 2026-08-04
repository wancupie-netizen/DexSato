"""
Tests for DexSato Dashboard Collection Service.

Responsibilities
----------------
- Verify request delegation
- Verify collection ordering
- Verify empty collection behavior
"""

from unittest.mock import Mock, call, patch

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
)

from adaptive.dashboard.dashboard_request import (
    DashboardRequest,
)

from application.dashboard_collection_service import (
    build_dashboard_collection,
)


# ==========================================================
# Multiple Requests
# ==========================================================

@patch(
    "application.dashboard_collection_service."
    "build_adaptive_dashboard"
)
def test_should_build_dashboard_collection(
    mock_build_adaptive_dashboard,
):
    """
    Service should build one DashboardCard
    for every DashboardRequest.
    """

    request_btc = Mock(
        spec=DashboardRequest,
    )

    request_eth = Mock(
        spec=DashboardRequest,
    )

    card_btc = Mock(
        spec=DashboardCard,
    )

    card_eth = Mock(
        spec=DashboardCard,
    )

    mock_build_adaptive_dashboard.side_effect = [
        card_btc,
        card_eth,
    ]

    result = build_dashboard_collection(

        requests=[
            request_btc,
            request_eth,
        ],

    )

    assert result == [
        card_btc,
        card_eth,
    ]

    assert mock_build_adaptive_dashboard.call_count == 2

    assert mock_build_adaptive_dashboard.call_args_list == [

        call(
            request_btc,
        ),

        call(
            request_eth,
        ),

    ]


# ==========================================================
# Ordering
# ==========================================================

@patch(
    "application.dashboard_collection_service."
    "build_adaptive_dashboard"
)
def test_should_preserve_request_order(
    mock_build_adaptive_dashboard,
):
    """
    Output order must match input request order.
    """

    requests = [

        Mock(
            spec=DashboardRequest,
        ),

        Mock(
            spec=DashboardRequest,
        ),

        Mock(
            spec=DashboardRequest,
        ),

    ]

    cards = [

        Mock(
            spec=DashboardCard,
        ),

        Mock(
            spec=DashboardCard,
        ),

        Mock(
            spec=DashboardCard,
        ),

    ]

    mock_build_adaptive_dashboard.side_effect = cards

    result = build_dashboard_collection(
        requests=requests,
    )

    assert result == cards


# ==========================================================
# Empty Collection
# ==========================================================

@patch(
    "application.dashboard_collection_service."
    "build_adaptive_dashboard"
)
def test_should_return_empty_collection(
    mock_build_adaptive_dashboard,
):
    """
    Empty request collection should return
    an empty DashboardCard collection.
    """

    result = build_dashboard_collection(
        requests=[],
    )

    assert result == []

    mock_build_adaptive_dashboard.assert_not_called()


# ==========================================================
# Iterable Support
# ==========================================================

@patch(
    "application.dashboard_collection_service."
    "build_adaptive_dashboard"
)
def test_should_accept_request_iterable(
    mock_build_adaptive_dashboard,
):
    """
    Service should accept any iterable,
    including generators.
    """

    request = Mock(
        spec=DashboardRequest,
    )

    card = Mock(
        spec=DashboardCard,
    )

    mock_build_adaptive_dashboard.return_value = card

    requests = (
        item
        for item in [
            request,
        ]
    )

    result = build_dashboard_collection(
        requests=requests,
    )

    assert result == [
        card,
    ]

    mock_build_adaptive_dashboard.assert_called_once_with(
        request,
    )