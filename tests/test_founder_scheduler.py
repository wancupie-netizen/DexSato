"""
Tests for the DexSato Founder Scheduler.
"""

from founder_scheduler import (
    build_change_summaries,
    deliver_change_digest,
    execute_founder_scheduler,
    load_previous_snapshot,
    run_founder_scheduler,
)


PREVIOUS_SNAPSHOT = {
    "generated_at": (
        "2026-07-25T00:00:00+00:00"
    ),
    "total_coins": 1,
    "available_coins": 1,
    "unavailable_coins": 0,
    "coins": [
        {
            "token": "BTC",
            "available": True,
            "decision": "IGNORE",
            "confidence": "LOW",
            "historical_success": 0.0,
            "seen_before": False,
            "reasons": [],
            "summary": (
                "Recommended action: IGNORE"
            ),
            "error": None,
        },
    ],
}


CURRENT_SNAPSHOT = {
    "generated_at": (
        "2026-07-25T06:00:00+00:00"
    ),
    "total_coins": 1,
    "available_coins": 1,
    "unavailable_coins": 0,
    "coins": [
        {
            "token": "BTC",
            "available": True,
            "decision": "WATCH",
            "confidence": "HIGH",
            "historical_success": 82.0,
            "seen_before": True,
            "reasons": [
                "PRICE_MOMENTUM",
                "STRONG_LIQUIDITY",
            ],
            "summary": (
                "Recommended action: WATCH"
            ),
            "error": None,
        },
    ],
}


MEANINGFUL_CHANGE = {
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
    "summary": (
        "Recommended action: WATCH"
    ),
    "triggers": [
        "DECISION_CHANGED",
        "CONFIDENCE_INCREASED",
        "EVIDENCE_ADDED",
    ],
}


SECOND_CHANGE = {
    **MEANINGFUL_CHANGE,
    "token": "ETH",
    "old_decision": "IGNORE",
    "new_decision": "REVIEW",
    "new_confidence": "MEDIUM",
    "seen_before": False,
    "historical_success": 0.0,
    "reasons": [
        "WEAK_BREAKOUT",
    ],
    "reasons_added": [
        "WEAK_BREAKOUT",
    ],
}


# ==========================================================
# Previous Snapshot Loading
# ==========================================================

def test_should_load_existing_previous_snapshot():
    """
    Existing snapshot should be used for comparison.
    """

    result = load_previous_snapshot(
        load_snapshot=(
            lambda: PREVIOUS_SNAPSHOT
        ),
    )

    assert result == PREVIOUS_SNAPSHOT


def test_should_accept_missing_previous_snapshot():
    """
    First automated run should create a baseline.
    """

    def missing_snapshot():
        raise FileNotFoundError(
            "Snapshot unavailable."
        )

    result = load_previous_snapshot(
        load_snapshot=missing_snapshot,
    )

    assert result is None


def test_should_not_hide_invalid_existing_snapshot():
    """
    Invalid existing snapshots should remain critical errors.
    """

    def invalid_snapshot():
        raise RuntimeError(
            "Snapshot contains invalid JSON."
        )

    try:

        load_previous_snapshot(
            load_snapshot=invalid_snapshot,
        )

    except RuntimeError as error:

        assert str(
            error,
        ) == (
            "Snapshot contains invalid JSON."
        )

    else:

        raise AssertionError(
            "RuntimeError was not raised."
        )


# ==========================================================
# Change Summaries
# ==========================================================

def test_should_build_console_change_summaries():
    """
    Console summaries should show token and transition.
    """

    result = build_change_summaries(
        [
            MEANINGFUL_CHANGE,
            SECOND_CHANGE,
        ],
    )

    assert result == [
        "BTC: IGNORE → WATCH",
        "ETH: IGNORE → REVIEW",
    ]


def test_should_normalize_change_summary_values():
    """
    Change summary values should be normalized for display.
    """

    result = build_change_summaries(
        [
            {
                "token": " eth ",
                "old_decision": " ignore ",
                "new_decision": " review ",
            },
        ],
    )

    assert result == [
        "ETH: IGNORE → REVIEW",
    ]


# ==========================================================
# Telegram Delivery
# ==========================================================

def test_should_mark_successful_digest_as_sent():
    """
    Successful Telegram delivery should become SENT.
    """

    received_changes = None

    def fake_send(
        *,
        changes,
    ):
        nonlocal received_changes

        received_changes = changes

        return {
            "success": True,
            "sent": True,
            "chat_id": "123456",
            "changes": 1,
        }

    result = deliver_change_digest(
        changes=[
            MEANINGFUL_CHANGE,
        ],
        send_digest=fake_send,
    )

    assert received_changes == [
        MEANINGFUL_CHANGE,
    ]

    assert result["success"] is True

    assert result["sent"] is True

    assert result["status"] == "SENT"

    assert result["error"] is None


def test_should_mark_empty_digest_as_skipped():
    """
    No meaningful changes should become SKIPPED.
    """

    def fake_send(
        *,
        changes,
    ):
        assert changes == []

        return {
            "success": True,
            "sent": False,
            "changes": 0,
        }

    result = deliver_change_digest(
        changes=[],
        send_digest=fake_send,
    )

    assert result["success"] is True

    assert result["sent"] is False

    assert result["status"] == "SKIPPED"

    assert result["error"] is None


def test_should_capture_telegram_failure():
    """
    Telegram failure must not propagate into the scan workflow.
    """

    def failing_send(
        *,
        changes,
    ):
        assert changes == [
            MEANINGFUL_CHANGE,
        ]

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not configured."
        )

    result = deliver_change_digest(
        changes=[
            MEANINGFUL_CHANGE,
        ],
        send_digest=failing_send,
    )

    assert result == {
        "success": False,
        "sent": False,
        "status": "FAILED",
        "changes": 1,
        "error": (
            "TELEGRAM_BOT_TOKEN "
            "is not configured."
        ),
    }


# ==========================================================
# Scheduler Workflow
# ==========================================================

def test_should_execute_scheduler_in_correct_order():
    """
    Previous snapshot must be read before generation and the
    current snapshot must be read afterwards.
    """

    calls: list[str] = []

    snapshots = iter(
        [
            PREVIOUS_SNAPSHOT,
            CURRENT_SNAPSHOT,
        ]
    )

    def fake_load():
        calls.append(
            "load",
        )

        return next(
            snapshots,
        )

    def fake_generate():
        calls.append(
            "generate",
        )

        return {
            "success": True,
            "snapshot_file": (
                "output/snapshots/"
                "latest_snapshot.json"
            ),
        }

    def fake_detect(
        *,
        previous_snapshot,
        current_snapshot,
    ):
        calls.append(
            "detect",
        )

        assert previous_snapshot == (
            PREVIOUS_SNAPSHOT
        )

        assert current_snapshot == (
            CURRENT_SNAPSHOT
        )

        return [
            MEANINGFUL_CHANGE,
        ]

    def fake_send(
        *,
        changes,
    ):
        calls.append(
            "send",
        )

        assert changes == [
            MEANINGFUL_CHANGE,
        ]

        return {
            "success": True,
            "sent": True,
            "changes": 1,
        }

    result = execute_founder_scheduler(
        load_snapshot=fake_load,
        generate_snapshot=fake_generate,
        detect_changes=fake_detect,
        send_digest=fake_send,
    )

    assert calls == [
        "load",
        "generate",
        "load",
        "detect",
        "send",
    ]

    assert result["success"] is True

    assert result["automation_status"] == (
        "HEALTHY"
    )

    assert result["meaningful_changes"] == 1

    assert result["change_summaries"] == [
        "BTC: IGNORE → WATCH",
    ]

    assert result["telegram_sent"] is True

    assert result["telegram_status"] == "SENT"

    assert result["telegram_error"] is None

    assert result["baseline_created"] is False


def test_should_create_baseline_without_initial_alert():
    """
    Missing previous snapshot should create a quiet baseline.
    """

    load_calls = 0

    def fake_load():
        nonlocal load_calls

        load_calls += 1

        if load_calls == 1:

            raise FileNotFoundError(
                "No previous snapshot."
            )

        return CURRENT_SNAPSHOT

    received_previous = "not-called"

    def fake_detect(
        *,
        previous_snapshot,
        current_snapshot,
    ):
        nonlocal received_previous

        received_previous = (
            previous_snapshot
        )

        assert current_snapshot == (
            CURRENT_SNAPSHOT
        )

        return []

    received_changes = None

    def fake_send(
        *,
        changes,
    ):
        nonlocal received_changes

        received_changes = changes

        return {
            "success": True,
            "sent": False,
            "changes": 0,
        }

    result = execute_founder_scheduler(
        load_snapshot=fake_load,
        generate_snapshot=lambda: {
            "success": True,
            "snapshot_file": (
                "output/snapshots/"
                "latest_snapshot.json"
            ),
        },
        detect_changes=fake_detect,
        send_digest=fake_send,
    )

    assert received_previous is None

    assert received_changes == []

    assert result["baseline_created"] is True

    assert result["meaningful_changes"] == 0

    assert result["change_summaries"] == []

    assert result["telegram_sent"] is False

    assert result["telegram_status"] == (
        "SKIPPED"
    )

    assert result["automation_status"] == (
        "HEALTHY"
    )


def test_should_remain_healthy_without_changes():
    """
    Unchanged market data should not send Telegram.
    """

    snapshots = iter(
        [
            PREVIOUS_SNAPSHOT,
            PREVIOUS_SNAPSHOT,
        ]
    )

    result = execute_founder_scheduler(
        load_snapshot=lambda: next(
            snapshots,
        ),
        generate_snapshot=lambda: {
            "success": True,
            "snapshot_file": "snapshot.json",
        },
        detect_changes=(
            lambda **_: []
        ),
        send_digest=(
            lambda *,
            changes: {
                "success": True,
                "sent": False,
                "changes": len(
                    changes,
                ),
            }
        ),
    )

    assert result["meaningful_changes"] == 0

    assert result["telegram_sent"] is False

    assert result["telegram_status"] == (
        "SKIPPED"
    )

    assert result["automation_status"] == (
        "HEALTHY"
    )


def test_should_preserve_success_when_telegram_fails():
    """
    Telegram failure should create a DEGRADED result without
    invalidating the snapshot.
    """

    snapshots = iter(
        [
            PREVIOUS_SNAPSHOT,
            CURRENT_SNAPSHOT,
        ]
    )

    def failing_send(
        *,
        changes,
    ):
        assert changes == [
            MEANINGFUL_CHANGE,
        ]

        raise RuntimeError(
            "401 Client Error: Unauthorized"
        )

    result = execute_founder_scheduler(
        load_snapshot=lambda: next(
            snapshots,
        ),
        generate_snapshot=lambda: {
            "success": True,
            "snapshot_file": (
                "output/snapshots/"
                "latest_snapshot.json"
            ),
        },
        detect_changes=(
            lambda **_: [
                MEANINGFUL_CHANGE,
            ]
        ),
        send_digest=failing_send,
    )

    assert result["success"] is True

    assert result["automation_status"] == (
        "DEGRADED"
    )

    assert result["meaningful_changes"] == 1

    assert result["telegram_sent"] is False

    assert result["telegram_status"] == (
        "FAILED"
    )

    assert result["telegram_error"] == (
        "401 Client Error: Unauthorized"
    )

    assert result["snapshot_file"] == (
        "output/snapshots/"
        "latest_snapshot.json"
    )


def test_should_return_snapshot_metadata():
    """
    Scheduler result should expose useful operating metadata.
    """

    snapshots = iter(
        [
            PREVIOUS_SNAPSHOT,
            CURRENT_SNAPSHOT,
        ]
    )

    result = execute_founder_scheduler(
        load_snapshot=lambda: next(
            snapshots,
        ),
        generate_snapshot=lambda: {
            "success": True,
            "snapshot_file": (
                "output/snapshots/"
                "latest_snapshot.json"
            ),
        },
        detect_changes=(
            lambda **_: [
                MEANINGFUL_CHANGE,
            ]
        ),
        send_digest=(
            lambda **_: {
                "success": True,
                "sent": True,
                "changes": 1,
            }
        ),
    )

    assert result["generated_at"] == (
        "2026-07-25T06:00:00+00:00"
    )

    assert result["total_coins"] == 1

    assert result["available_coins"] == 1

    assert result["unavailable_coins"] == 0

    assert result["snapshot_file"] == (
        "output/snapshots/"
        "latest_snapshot.json"
    )


def test_should_reject_invalid_change_detector_result():
    """
    Change detector must return a list.
    """

    snapshots = iter(
        [
            PREVIOUS_SNAPSHOT,
            CURRENT_SNAPSHOT,
        ]
    )

    try:

        execute_founder_scheduler(
            load_snapshot=lambda: next(
                snapshots,
            ),
            generate_snapshot=lambda: {
                "success": True,
                "snapshot_file": (
                    "output/snapshots/"
                    "latest_snapshot.json"
                ),
            },
            detect_changes=(
                lambda **_: None
            ),
            send_digest=(
                lambda **_: {
                    "success": True,
                    "sent": False,
                }
            ),
        )

    except RuntimeError as error:

        assert str(
            error,
        ) == (
            "Meaningful change detector "
            "returned invalid data."
        )

    else:

        raise AssertionError(
            "RuntimeError was not raised."
        )


# ==========================================================
# Command Exit Codes
# ==========================================================

def test_should_return_zero_for_healthy_run():
    """
    Healthy automated cycle should return exit code zero.
    """

    result = run_founder_scheduler(
        execute=lambda: {
            "success": True,
            "automation_status": "HEALTHY",
            "baseline_created": False,
            "generated_at": (
                "2026-07-25T06:00:00+00:00"
            ),
            "total_coins": 10,
            "available_coins": 10,
            "unavailable_coins": 0,
            "meaningful_changes": 0,
            "change_summaries": [],
            "telegram_sent": False,
            "telegram_status": "SKIPPED",
            "telegram_error": None,
            "snapshot_file": (
                "output/snapshots/"
                "latest_snapshot.json"
            ),
        },
    )

    assert result == 0


def test_should_persist_completed_run_for_dashboard():
    """
    A successful run should publish its status for the dashboard.
    """

    execution_result = {
        "success": True,
        "automation_status": "HEALTHY",
        "telegram_status": "SKIPPED",
    }
    persisted = []

    result = run_founder_scheduler(
        execute=lambda: execution_result,
        persist_result=persisted.append,
    )

    assert result == 0
    assert persisted == [
        execution_result,
    ]


def test_should_return_zero_for_degraded_telegram_run():
    """
    Telegram failure must still return exit code zero when the
    snapshot and comparison completed.
    """

    result = run_founder_scheduler(
        execute=lambda: {
            "success": True,
            "automation_status": "DEGRADED",
            "baseline_created": False,
            "generated_at": (
                "2026-07-25T06:00:00+00:00"
            ),
            "total_coins": 10,
            "available_coins": 10,
            "unavailable_coins": 0,
            "meaningful_changes": 1,
            "change_summaries": [
                "BTC: IGNORE → WATCH",
            ],
            "telegram_sent": False,
            "telegram_status": "FAILED",
            "telegram_error": (
                "401 Client Error: Unauthorized"
            ),
            "snapshot_file": (
                "output/snapshots/"
                "latest_snapshot.json"
            ),
        },
    )

    assert result == 0


def test_should_return_one_when_critical_automation_fails():
    """
    Snapshot or comparison failures should return a non-zero
    exit code.
    """

    def failing_execution():
        raise RuntimeError(
            "Automated scan failed."
        )

    result = run_founder_scheduler(
        execute=failing_execution,
    )

    assert result == 1
