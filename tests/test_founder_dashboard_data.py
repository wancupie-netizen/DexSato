"""
Tests for Founder Dashboard Shared Data.
"""

from datetime import (
    datetime,
    timezone,
)

import pytest

from adaptive.dashboard.dashboard_card import (
    create_dashboard_card,
)

from application.founder_dashboard_data import (
    serialize_founder_dashboard_results,
)


def build_test_card():
    """
    Build one reusable DashboardCard.
    """

    return create_dashboard_card(
        token="BTC",
        decision="WATCH",
        confidence="HIGH",
        historical_success=66.67,
        seen_before=True,
        reasons=[
            "STRONG_LIQUIDITY",
        ],
        summary="Momentum detected.",
        last_updated=datetime.now(
            timezone.utc,
        ),
    )


def test_should_serialize_available_coin():
    """
    Available cards should become JSON-safe data.
    """

    result = serialize_founder_dashboard_results(
        [
            {
                "token": "BTC",
                "card": build_test_card(),
                "market": {
                    "pair": "BTC/USDT",
                    "price": "64202.82",
                    "liquidity": 15149834.19,
                    "volume_24h": 16594948.71,
                    "market_cap": 4194770084,
                    "fdv": 4194770084,
                    "pair_address": "0xpool",
                    "chain": "bsc",
                    "source": "DexScreener",
                },
                "error": None,
            }
        ]
    )[0]

    assert result["token"] == "BTC"

    assert result["available"] is True

    assert result["pair"] == "BTC/USDT"

    assert result["price"] == "64202.82"

    assert result["liquidity"] == 15149834.19

    assert result["source"] == "DexScreener"

    assert result["decision"] == "WATCH"

    assert result["confidence"] == "HIGH"

    assert result["historical_success"] == 66.67

    assert result["seen_before"] is True

    assert result["reasons"] == [
        "STRONG_LIQUIDITY",
    ]

    assert "Liquidity is currently supportive" in result["risk_note"]

    assert result["error"] is None


def test_should_serialize_unavailable_coin():
    """
    Failed scans should remain visible.
    """

    result = serialize_founder_dashboard_results(
        [
            {
                "token": "ETH",
                "card": None,
                "error": "Scan unavailable.",
            }
        ]
    )[0]

    assert result["token"] == "ETH"

    assert result["available"] is False

    assert result["pair"] is None

    assert result["price"] is None

    assert result["decision"] is None

    assert result["error"] == (
        "Scan unavailable."
    )


def test_should_serialize_gold_as_reference_only():
    result = serialize_founder_dashboard_results(
        [
            {
                "token": "XAU",
                "card": None,
                "reference_only": True,
                "reference_intelligence": {
                    "market_state": "UPPER_RANGE",
                    "daily_change_pct": 0.5,
                    "intraday_range_pct": 1.25,
                    "range_position_pct": 75.0,
                    "evidence": ["ABOVE_OPEN", "UPPER_RANGE"],
                    "summary": "Objective gold reference intelligence.",
                },
                "market": {
                    "pair": "XAU/USD",
                    "price": "4073.39",
                    "liquidity": None,
                    "volume_24h": None,
                    "market_cap": None,
                    "fdv": None,
                    "pair_address": "twelvedata:XAU/USD",
                    "chain": "spot-metals",
                    "source": "Twelve Data",
                },
                "error": None,
            }
        ]
    )[0]

    assert result["available"] is True
    assert result["decision"] == "REFERENCE"
    assert result["confidence"] == "REFERENCE"
    assert result["asset_class"] == "commodities"
    assert result["liquidity"] is None
    assert result["historical_success"] is None
    assert result["market_state"] == "UPPER_RANGE"
    assert result["daily_change_pct"] == 0.5
    assert result["reference_evidence"] == [
        "ABOVE_OPEN",
        "UPPER_RANGE",
    ]
    assert "upper end of today's range" in result["risk_note"]


def test_should_reject_invalid_collection():
    """
    Shared data requires a list.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Founder dashboard results must be a list"
        ),
    ):
        serialize_founder_dashboard_results(
            None,
        )
