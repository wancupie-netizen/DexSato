"""
Tests for AlphaRadar Telegram Notifier.
"""

import pytest

from application.telegram_notifier import (
    build_change_digest_message,
    build_telegram_message,
    humanize_evidence,
    send_change_digest,
    send_telegram_alert,
)


DASHBOARD_DATA = [
    {
        "token": "BTC",
        "available": True,
        "decision": "WATCH",
        "confidence": "HIGH",
        "historical_success": 66.67,
        "seen_before": True,
        "reasons": [
            "STRONG_LIQUIDITY",
            "PRICE_MOMENTUM",
        ],
        "summary": "Momentum detected.",
        "error": None,
    },
    {
        "token": "ETH",
        "available": False,
        "decision": None,
        "confidence": None,
        "historical_success": None,
        "seen_before": False,
        "reasons": [],
        "summary": None,
        "error": "Dashboard unavailable.",
    },
]


SINGLE_CHANGE = {
    "token": "BTC",
    "old_decision": "IGNORE",
    "new_decision": "WATCH",
    "old_confidence": "LOW",
    "new_confidence": "HIGH",
    "reasons": [
        "PRICE_MOMENTUM",
        "STRONG_LIQUIDITY",
    ],
    "reasons_added": [
        "PRICE_MOMENTUM",
        "STRONG_LIQUIDITY",
    ],
    "historical_success": 82.0,
    "seen_before": True,
    "summary": "Momentum detected.",
    "triggers": [
        "DECISION_CHANGED",
        "CONFIDENCE_INCREASED",
        "EVIDENCE_ADDED",
    ],
}


class FakeResponse:
    """
    Minimal successful requests response.
    """

    def raise_for_status(
        self,
    ) -> None:
        return None


# ==========================================================
# Evidence Translation
# ==========================================================

def test_should_humanize_evidence():
    """
    Technical evidence should be readable by users.
    """

    assert humanize_evidence(
        "PRICE_MOMENTUM",
    ) == "Momentum improving"

    assert humanize_evidence(
        "STRONG_LIQUIDITY",
    ) == "Liquidity increasing"

    assert humanize_evidence(
        "RISKY_ACTIVITY",
    ) == (
        "Risky market activity detected"
    )

    assert humanize_evidence(
        "WEAK_BREAKOUT",
    ) == "Weak breakout"

    assert humanize_evidence(
        "CUSTOM_SIGNAL",
    ) == "Custom signal"


# ==========================================================
# Meaningful Change Digest
# ==========================================================

def test_should_build_single_change_digest():
    """
    One change should create one focused notification.
    """

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
        ],
    )

    assert "📡 DexSato Market Update" in message

    assert (
        "🟡 1 market changed"
        in message
    )

    assert "🔵 BTC · WATCH" in message

    assert "Change: IGNORE → WATCH" in message

    assert "Why it changed" in message

    assert (
        "• Momentum improving"
        in message
    )

    assert (
        "• Liquidity increasing"
        in message
    )

    assert (
        "Confidence: 🟢 HIGH"
        in message
    )

    assert (
        "Pattern: 📚 Seen before · "
        "82% historical success"
        in message
    )

    assert (
        "Founder action: Keep on the watchlist"
        in message
    )

    assert "━━━━━━━━━━━━━━━━━━" not in message


def test_should_build_new_pattern_message():
    """
    New market behaviour should use the V1 history label.
    """

    change = {
        **SINGLE_CHANGE,
        "token": "ETH",
        "old_decision": "IGNORE",
        "new_decision": "REVIEW",
        "new_confidence": "MEDIUM",
        "reasons_added": [
            "WEAK_BREAKOUT",
        ],
        "seen_before": False,
        "historical_success": 0.0,
    }

    message = build_change_digest_message(
        [
            change,
        ],
    )

    assert "🟡 ETH" in message

    assert "IGNORE → REVIEW" in message

    assert "• Weak breakout" in message

    assert (
        "Confidence: 🟡 MEDIUM"
        in message
    )

    assert "Pattern: 🆕 New pattern" in message

    assert (
        "Founder action: Review the latest evidence"
        in message
    )


def test_should_build_multiple_change_digest():
    """
    Several changes should become one digest.
    """

    second_change = {
        **SINGLE_CHANGE,
        "token": "ETH",
        "old_decision": "REVIEW",
        "new_decision": "SELL",
        "new_confidence": "MEDIUM",
        "reasons_added": [
            "RISKY_ACTIVITY",
        ],
        "seen_before": False,
    }

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
            second_change,
        ],
    )

    assert "🔵 BTC" in message

    assert "🔴 ETH" in message

    assert "IGNORE → WATCH" in message

    assert "REVIEW → SELL" in message

    assert (
        "🟡 2 markets changed"
        in message
    )

    assert "━━━━━━━━━━━━━━━━━━" not in message

    assert "Founder action: Review current exposure" in message


def test_should_use_higher_activity_indicator():
    """
    Larger digest activity should use stronger indicators.
    """

    medium_changes = [
        {
            **SINGLE_CHANGE,
            "token": f"COIN{index}",
        }
        for index in range(
            3,
        )
    ]

    high_changes = [
        {
            **SINGLE_CHANGE,
            "token": f"MARKET{index}",
        }
        for index in range(
            6,
        )
    ]

    medium_message = (
        build_change_digest_message(
            medium_changes,
        )
    )

    high_message = (
        build_change_digest_message(
            high_changes,
        )
    )

    assert (
        "🟠 3 markets changed"
        in medium_message
    )

    assert (
        "🔴 6 markets changed"
        in high_message
    )


def test_should_limit_digest_changes():
    """
    Digest should respect the maximum alert size.
    """

    changes = [
        {
            **SINGLE_CHANGE,
            "token": f"COIN{index}",
        }
        for index in range(
            3,
        )
    ]

    message = build_change_digest_message(
        changes,
        max_changes=2,
    )

    assert "COIN0" in message

    assert "COIN1" in message

    assert "COIN2" not in message

    assert (
        "➕ 1 additional change in dashboard"
        in message
    )

    assert (
        "🟠 3 markets changed"
        in message
    )


def test_should_hide_local_dashboard_url():
    """
    Loopback dashboard URLs must not appear in Telegram.
    """

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
        ],
        dashboard_url=(
            "http://127.0.0.1:8000"
        ),
    )

    assert "Open dashboard" not in message

    assert "127.0.0.1" not in message


def test_should_hide_localhost_dashboard_url():
    """
    Localhost dashboard URLs must not appear in Telegram.
    """

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
        ],
        dashboard_url=(
            "http://localhost:8000"
        ),
    )

    assert "Open dashboard" not in message

    assert "localhost" not in message


def test_should_include_public_dashboard_url():
    """
    Public dashboard URLs should remain future-ready.
    """

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
        ],
        dashboard_url=(
            "https://app.dexsato.com/"
        ),
    )

    assert "🔗 Dashboard:" in message

    assert (
        "https://app.dexsato.com"
        in message
    )

    assert (
        "https://app.dexsato.com/"
        not in message
    )


def test_should_read_public_dashboard_url_from_environment(
    monkeypatch,
):
    """
    Public dashboard URL should be read from the standardized
    environment variable.
    """

    monkeypatch.setenv(
        "PUBLIC_DASHBOARD_URL",
        "https://app.dexsato.com/",
    )

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
        ],
    )

    assert "🔗 Dashboard:" in message

    assert (
        "https://app.dexsato.com"
        in message
    )


def test_should_ignore_legacy_dashboard_environment_variable(
    monkeypatch,
):
    """
    The retired AlphaRadar-specific dashboard variable should
    no longer control Telegram messages.
    """

    monkeypatch.delenv(
        "PUBLIC_DASHBOARD_URL",
        raising=False,
    )

    monkeypatch.setenv(
        "ALPHARADAR_DASHBOARD_URL",
        "https://legacy.example",
    )

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
        ],
    )

    assert "legacy.example" not in message

    assert "Open dashboard" not in message


def test_should_hide_invalid_dashboard_url():
    """
    Invalid dashboard values must not be shown.
    """

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
        ],
        dashboard_url="alpharadar-dashboard",
    )

    assert "Open dashboard" not in message

    assert (
        "alpharadar-dashboard"
        not in message
    )


def test_should_return_empty_message_for_no_changes():
    """
    Silence is required when nothing meaningful changed.
    """

    assert build_change_digest_message(
        [],
    ) == ""


def test_should_reject_invalid_change_collection():
    """
    Digest input must be a list of dictionaries.
    """

    with pytest.raises(
        ValueError,
        match="Changes must be a list",
    ):

        build_change_digest_message(
            None,
        )

    with pytest.raises(
        ValueError,
        match="Changes contain invalid data",
    ):

        build_change_digest_message(
            [
                "invalid",
            ],
        )

    with pytest.raises(
        ValueError,
        match=(
            "Maximum digest changes "
            "must be at least one"
        ),
    ):

        build_change_digest_message(
            [
                SINGLE_CHANGE,
            ],
            max_changes=0,
        )


# ==========================================================
# Digest Sending
# ==========================================================

def test_should_send_change_digest():
    """
    Meaningful digest should call Telegram once.
    """

    calls: list[
        dict[str, object]
    ] = []

    def fake_post(
        url,
        *,
        json,
        timeout,
    ):

        calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )

        return FakeResponse()

    result = send_change_digest(
        changes=[
            SINGLE_CHANGE,
        ],
        bot_token="test-token",
        chat_id="123456",
        post=fake_post,
    )

    assert result == {
        "success": True,
        "sent": True,
        "chat_id": "123456",
        "changes": 1,
    }

    assert len(
        calls,
    ) == 1

    assert calls[0]["url"] == (
        "https://api.telegram.org/"
        "bottest-token/sendMessage"
    )

    message = calls[0][
        "json"
    ][
        "text"
    ]

    assert (
        "📡 DexSato Market Update"
        in message
    )

    assert "🔵 BTC" in message

    assert "IGNORE → WATCH" in message

    assert (
        calls[0]["json"][
            "disable_web_page_preview"
        ]
        is True
    )

    assert calls[0]["timeout"] == 15


def test_should_remain_silent_without_changes():
    """
    Empty changes must not call Telegram or need credentials.
    """

    calls = 0

    def fake_post(
        *args,
        **kwargs,
    ):

        nonlocal calls

        calls += 1

        return FakeResponse()

    result = send_change_digest(
        changes=[],
        bot_token="",
        chat_id="",
        post=fake_post,
    )

    assert result == {
        "success": True,
        "sent": False,
        "changes": 0,
    }

    assert calls == 0


# ==========================================================
# Legacy Manual Snapshot
# ==========================================================

def test_should_build_legacy_telegram_message():
    """
    Legacy manual message should remain available.
    """

    message = build_telegram_message(
        DASHBOARD_DATA,
    )

    assert (
        "DexSato Founder Alert"
        in message
    )

    assert (
        "2 markets. One engine."
        in message
    )

    assert "BTC" in message

    assert "WATCH" in message

    assert "HIGH" in message

    assert "67%" in message

    assert (
        "Liquidity increasing"
        in message
    )

    assert "ETH" in message

    assert "UNAVAILABLE" in message


def test_should_reject_invalid_legacy_market_data():
    """
    Legacy dashboard items must remain dictionaries.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Dashboard data contains "
            "invalid market data"
        ),
    ):

        build_telegram_message(
            [
                "invalid",
            ],
        )


def test_should_send_legacy_telegram_alert():
    """
    Legacy notifier should call Telegram sendMessage once.
    """

    calls: list[
        dict[str, object]
    ] = []

    def fake_post(
        url,
        *,
        json,
        timeout,
    ):

        calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
            }
        )

        return FakeResponse()

    result = send_telegram_alert(
        dashboard_data=DASHBOARD_DATA,
        bot_token="test-token",
        chat_id="123456",
        post=fake_post,
    )

    assert result == {
        "success": True,
        "chat_id": "123456",
        "coins": 2,
    }

    assert len(
        calls,
    ) == 1

    assert calls[0]["url"] == (
        "https://api.telegram.org/"
        "bottest-token/sendMessage"
    )

    assert (
        calls[0]["json"][
            "chat_id"
        ]
        == "123456"
    )

    assert (
        "BTC"
        in calls[0]["json"]["text"]
    )

    assert calls[0]["timeout"] == 15


# ==========================================================
# Credentials
# ==========================================================

def test_should_reject_missing_bot_token(
    monkeypatch,
):
    """
    Bot token is required when a message is sent.
    """

    monkeypatch.delenv(
        "TELEGRAM_BOT_TOKEN",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TELEGRAM_BOT_TOKEN "
            "is not configured"
        ),
    ):

        send_change_digest(
            changes=[
                SINGLE_CHANGE,
            ],
            bot_token="",
            chat_id="123456",
        )


def test_should_reject_missing_chat_id(
    monkeypatch,
):
    """
    Chat ID is required when a message is sent.
    """

    monkeypatch.delenv(
        "TELEGRAM_CHAT_ID",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TELEGRAM_CHAT_ID "
            "is not configured"
        ),
    ):

        send_change_digest(
            changes=[
                SINGLE_CHANGE,
            ],
            bot_token="test-token",
            chat_id="",
        )
