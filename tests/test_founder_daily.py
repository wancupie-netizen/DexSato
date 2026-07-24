"""
Tests for the AlphaRadar Founder Daily command.
"""

from founder_daily import (
    build_decision_counts,
    confirm_telegram_send,
    run_founder_daily,
)


SNAPSHOT = {
    "generated_at": (
        "2026-07-25T00:00:00+00:00"
    ),
    "total_coins": 3,
    "available_coins": 2,
    "unavailable_coins": 1,
    "coins": [
        {
            "token": "BTC",
            "available": True,
            "decision": "WATCH",
            "confidence": "HIGH",
        },
        {
            "token": "ETH",
            "available": True,
            "decision": "IGNORE",
            "confidence": "LOW",
        },
        {
            "token": "TEST",
            "available": False,
            "decision": None,
            "confidence": None,
            "error": "Unavailable.",
        },
    ],
}


def test_should_count_snapshot_decisions():
    """
    Decision counts should include unavailable markets.
    """

    counts = build_decision_counts(
        SNAPSHOT["coins"],
    )

    assert counts["WATCH"] == 1

    assert counts["IGNORE"] == 1

    assert counts["UNAVAILABLE"] == 1


def test_should_confirm_telegram_for_yes():
    """
    Y or yes should confirm Telegram sending.
    """

    assert confirm_telegram_send(
        ask=lambda _: "y",
    ) is True

    assert confirm_telegram_send(
        ask=lambda _: "YES",
    ) is True


def test_should_reject_telegram_by_default():
    """
    Empty or negative answers should skip Telegram.
    """

    assert confirm_telegram_send(
        ask=lambda _: "",
    ) is False

    assert confirm_telegram_send(
        ask=lambda _: "n",
    ) is False


def test_should_generate_snapshot_and_skip_telegram():
    """
    Founder may generate a snapshot without sending it.
    """

    calls = {
        "generate": 0,
        "load": 0,
        "send": 0,
    }

    def fake_generate():
        calls["generate"] += 1

        return {
            "success": True,
            "snapshot_file": (
                "output/snapshots/"
                "latest_snapshot.json"
            ),
        }

    def fake_load():
        calls["load"] += 1

        return SNAPSHOT

    def fake_send(
        *,
        dashboard_data,
    ):
        calls["send"] += 1

        return {
            "success": True,
        }

    result = run_founder_daily(
        generate_snapshot=fake_generate,
        load_snapshot=fake_load,
        send_alert=fake_send,
        ask=lambda _: "n",
    )

    assert result == 0

    assert calls == {
        "generate": 1,
        "load": 1,
        "send": 0,
    }


def test_should_generate_and_send_telegram():
    """
    Founder confirmation should send stored snapshot data.
    """

    received_data = None

    def fake_generate():
        return {
            "success": True,
            "snapshot_file": (
                "output/snapshots/"
                "latest_snapshot.json"
            ),
        }

    def fake_load():
        return SNAPSHOT

    def fake_send(
        *,
        dashboard_data,
    ):
        nonlocal received_data

        received_data = dashboard_data

        return {
            "success": True,
            "chat_id": "12345",
            "coins": 3,
        }

    result = run_founder_daily(
        generate_snapshot=fake_generate,
        load_snapshot=fake_load,
        send_alert=fake_send,
        ask=lambda _: "y",
    )

    assert result == 0

    assert received_data == (
        SNAPSHOT["coins"]
    )


def test_should_return_failure_when_snapshot_fails():
    """
    Snapshot failure should stop before Telegram.
    """

    def failing_generate():
        raise RuntimeError(
            "Scan failed."
        )

    result = run_founder_daily(
        generate_snapshot=failing_generate,
        load_snapshot=lambda: SNAPSHOT,
        send_alert=lambda **_: {
            "success": True,
        },
        ask=lambda _: "y",
    )

    assert result == 1


def test_should_return_failure_when_telegram_fails():
    """
    Telegram failure should return a non-zero exit code.
    """

    def failing_send(
        *,
        dashboard_data,
    ):
        raise RuntimeError(
            "Telegram unavailable."
        )

    result = run_founder_daily(
        generate_snapshot=lambda: {
            "success": True,
        },
        load_snapshot=lambda: SNAPSHOT,
        send_alert=failing_send,
        ask=lambda _: "y",
    )

    assert result == 1