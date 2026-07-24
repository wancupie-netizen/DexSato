"""
AlphaRadar V1 Acceptance Tests.

These tests verify the complete V1 founder journey.

Production Features Verified
----------------------------
- Stable ten-coin production universe
- Shared dashboard data
- Telegram message builder
- Founder README
- Root project launcher
"""

from pathlib import Path

from application.founder_dashboard_data import (
    serialize_founder_dashboard_results,
)

from application.founder_dashboard_service import (
    FOUNDER_TOKENS,
    V1_ACTIVE_TOKENS,
)

from application.telegram_notifier import (
    build_telegram_message,
)


# ==========================================================
# V1 Active Tokens
# ==========================================================

def test_should_support_official_founder_tokens():
    """
    AlphaRadar V1 must support the approved ten-coin
    production universe.
    """

    expected_tokens = (
        "BTC",
        "ETH",
        "BNB",
        "XRP",
        "SOL",
        "DOGE",
        "ADA",
        "SUI",
        "LINK",
        "AVAX",
    )

    assert V1_ACTIVE_TOKENS == expected_tokens

    assert FOUNDER_TOKENS == expected_tokens

    assert len(
        FOUNDER_TOKENS,
    ) == 10


# ==========================================================
# Shared Dashboard Data
# ==========================================================

def test_should_build_shared_dashboard_data():
    """
    Shared dashboard data should preserve token ordering
    and unavailable market states.
    """

    dashboard = serialize_founder_dashboard_results(
        [
            {
                "token": "BTC",
                "card": None,
                "error": "Unavailable",
            },
            {
                "token": "ETH",
                "card": None,
                "error": "Unavailable",
            },
        ]
    )

    assert dashboard[0]["token"] == "BTC"

    assert dashboard[1]["token"] == "ETH"

    assert dashboard[0]["available"] is False

    assert dashboard[1]["available"] is False

    assert dashboard[0]["error"] == (
        "Unavailable"
    )

    assert dashboard[1]["error"] == (
        "Unavailable"
    )


# ==========================================================
# Telegram Message
# ==========================================================

def test_should_build_founder_telegram_message():
    """
    Telegram message should contain the current
    AlphaRadar market intelligence.
    """

    dashboard = [
        {
            "token": "BTC",
            "available": True,
            "decision": "WATCH",
            "confidence": "HIGH",
            "historical_success": 66.67,
            "seen_before": True,
            "reasons": [
                "ACCUMULATION",
            ],
            "summary": "Bullish",
            "error": None,
        }
    ]

    message = build_telegram_message(
        dashboard,
    )

    assert "BTC" in message

    assert "WATCH" in message

    assert "HIGH" in message

    assert "66.67%" in message

    assert "ACCUMULATION" in message


# ==========================================================
# README
# ==========================================================

def test_should_have_founder_readme():
    """
    Founder documentation must exist at project root.
    """

    readme = Path(
        "README.md",
    )

    assert readme.exists()

    assert readme.is_file()


# ==========================================================
# Project Launcher
# ==========================================================

def test_should_have_root_launcher():
    """
    AlphaRadar V1 should expose one simple root launcher.
    """

    launcher = Path(
        "main.py",
    )

    assert launcher.exists()

    assert launcher.is_file()