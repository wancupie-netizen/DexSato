"""
Tests for DexSato Founder Dashboard Presenter.
"""

from datetime import datetime, timezone

import pytest

from adaptive.dashboard.dashboard_card import (
    create_dashboard_card,
)

from presentation.founder_dashboard_presenter import (
    render_founder_coin_card,
    render_founder_dashboard,
)


def build_test_card(
    token: str = "BTC",
):
    """
    Build one reusable DashboardCard.
    """

    return create_dashboard_card(

        token=token,

        decision="WATCH",

        confidence="HIGH",

        historical_success=66.67,

        seen_before=True,

        reasons=[
            "STRONG_LIQUIDITY",
            "PRICE_MOMENTUM",
        ],

        summary="Momentum remains constructive.",

        last_updated=datetime.now(
            timezone.utc,
        ),

    )


def test_should_render_successful_coin_card():
    """
    Coin card should expose engine intelligence.
    """

    html = render_founder_coin_card(

        token="BTC",

        card=build_test_card(),

        error=None,

    )

    assert "BTC" in html

    assert "WATCH" in html

    assert "HIGH" in html

    assert "66.67%" in html

    assert "KNOWN PATTERN" in html

    assert "STRONG_LIQUIDITY" in html


def test_should_render_unavailable_coin_card():
    """
    Failed coin should remain visible.
    """

    html = render_founder_coin_card(

        token="ETH",

        card=None,

        error="Dashboard unavailable.",

    )

    assert "ETH" in html

    assert "UNAVAILABLE" in html

    assert "Dashboard unavailable." in html


def test_should_render_five_coin_dashboard():
    """
    Founder Dashboard should display all supplied coins.
    """

    results = [

        {
            "token": token,
            "card": build_test_card(
                token,
            ),
            "error": None,
        }

        for token in (
            "BTC",
            "ETH",
            "SOL",
            "XRP",
            "SUI",
        )
    ]

    html = render_founder_dashboard(
        results,
    )

    assert "<!DOCTYPE html>" in html

    assert "DexSato Market Intelligence" in html

    assert "BTC" in html

    assert "ETH" in html

    assert "SOL" in html

    assert "XRP" in html

    assert "SUI" in html

    assert html.count(
        "founder-coin-card"
    ) >= 5


def test_should_escape_dynamic_values():
    """
    Presenter must escape data-derived values.
    """

    html = render_founder_coin_card(

        token="<BTC>",

        card=None,

        error="<script>alert(1)</script>",

    )

    assert "<BTC>" not in html

    assert "&lt;BTC&gt;" in html

    assert "<script>" not in html

    assert "&lt;script&gt;" in html


def test_should_reject_invalid_result_collection():
    """
    Presenter requires a result list.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Founder dashboard results must be a list"
        ),
    ):

        render_founder_dashboard(
            None,
        )