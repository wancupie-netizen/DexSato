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
        "CUSTOM_SIGNAL",
    ) == "Custom signal"


# ==========================================================
# Meaningful Change Digest
# ==========================================================

def test_should_build_single_change_digest():
    """
    One change should create one focused alert.
    """

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
        ],
        dashboard_url=(
            "https://alpha.example/dashboard"
        ),
    )

    assert "📡 AlphaRadar" in message

    assert "BTC moved to WATCH" in message

    assert "IGNORE → WATCH" in message

    assert "Why?" in message

    assert (
        "• Momentum improving"
        in message
    )

    assert (
        "• Liquidity increasing"
        in message
    )

    assert "Confidence\nHIGH" in message

    assert "Seen before\nYes (82%)" in message

    assert "Open dashboard" in message

    assert (
        "https://alpha.example/dashboard"
        in message
    )


def test_should_build_new_pattern_message():
    """
    New market behaviour should be described naturally.
    """

    change = {
        **SINGLE_CHANGE,
        "token": "ETH",
        "seen_before": False,
        "historical_success": 0.0,
    }

    message = build_change_digest_message(
        [
            change,
        ],
    )

    assert (
        "No — new market behaviour"
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
        "new_decision": "WATCH",
        "new_confidence": "MEDIUM",
        "reasons_added": [
            "RISKY_ACTIVITY",
        ],
    }

    message = build_change_digest_message(
        [
            SINGLE_CHANGE,
            second_change,
        ],
    )

    assert "2 markets changed" in message

    assert "BTC moved to WATCH" in message

    assert "ETH moved to WATCH" in message

    assert "━━━━━━━━━━" in message


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

    assert "+ 1 more market changes" in message


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

    calls: list[dict[str, object]] = []

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

    assert (
        "BTC moved to WATCH"
        in calls[0]["json"]["text"]
    )

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

    assert "AlphaRadar Founder Alert" in message

    assert "2 markets. One engine." in message

    assert "BTC" in message

    assert "WATCH" in message

    assert "HIGH" in message

    assert "67%" in message

    assert "Liquidity increasing" in message

    assert "ETH" in message

    assert "UNAVAILABLE" in message


def test_should_send_legacy_telegram_alert():
    """
    Legacy notifier should call Telegram sendMessage once.
    """

    calls: list[dict[str, object]] = []

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

    assert calls[0]["json"]["chat_id"] == (
        "123456"
    )

    assert "BTC" in calls[0]["json"]["text"]

    assert calls[0]["timeout"] == 15


# ==========================================================
# Credentials
# ==========================================================

def test_should_reject_missing_bot_token():
    """
    Bot token is required when a message is sent.
    """

    with pytest.raises(
        RuntimeError,
        match=(
            "TELEGRAM_BOT_TOKEN is not configured"
        ),
    ):

        send_change_digest(
            changes=[
                SINGLE_CHANGE,
            ],
            bot_token="",
            chat_id="123456",
        )


def test_should_reject_missing_chat_id():
    """
    Chat ID is required when a message is sent.
    """

    with pytest.raises(
        RuntimeError,
        match=(
            "TELEGRAM_CHAT_ID is not configured"
        ),
    ):

        send_change_digest(
            changes=[
                SINGLE_CHANGE,
            ],
            bot_token="test-token",
            chat_id="",
        )