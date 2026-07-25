"""
AlphaRadar Founder Scheduler.

Single-run automated V1 workflow:

    python founder_scheduler.py

The command:

1. Reads the previous stored snapshot when available.
2. Generates a fresh ten-coin snapshot.
3. Compares the previous and current snapshots.
4. Sends a Telegram digest only for meaningful changes.
5. Preserves a successful snapshot when Telegram is unavailable.
6. Exits after one completed run.

Windows Task Scheduler will invoke this command at the
approved V1 scan times.

Environment variables
---------------------
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
ALPHARADAR_DASHBOARD_URL

Failure policy
--------------
Snapshot generation and snapshot comparison are critical.

Telegram delivery is non-critical. A Telegram configuration,
network, or API failure produces a DEGRADED result but does
not invalidate the newly generated snapshot.

This module does NOT:
- run continuously
- contain its own clock scheduler
- prompt the founder for confirmation
- send the complete ten-coin technical report
- retry failed runs
- manage Windows Task Scheduler
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from application.change_detector import (
    detect_meaningful_changes,
)

from application.founder_snapshot_service import (
    generate_latest_snapshot,
    read_latest_snapshot,
)

from application.telegram_notifier import (
    send_change_digest,
)


# ==========================================================
# Configuration
# ==========================================================

CONSOLE_WIDTH = 60


# ==========================================================
# Snapshot Loading
# ==========================================================

def load_previous_snapshot(
    *,
    load_snapshot: Callable[
        [],
        dict[str, Any],
    ] = read_latest_snapshot,
) -> dict[str, Any] | None:
    """
    Load the previous snapshot when one exists.

    A missing snapshot is expected during the first automated
    run and becomes the initial comparison baseline.
    """

    try:

        return load_snapshot()

    except FileNotFoundError:

        return None


# ==========================================================
# Change Presentation
# ==========================================================

def build_change_summaries(
    changes: list[dict[str, object]],
) -> list[str]:
    """
    Build concise console summaries for detected changes.
    """

    summaries: list[str] = []

    for change in changes:

        token = str(
            change.get(
                "token",
                "UNKNOWN",
            )
        ).strip().upper()

        old_decision = str(
            change.get(
                "old_decision",
                "UNKNOWN",
            )
        ).strip().upper()

        new_decision = str(
            change.get(
                "new_decision",
                "UNKNOWN",
            )
        ).strip().upper()

        summaries.append(
            (
                f"{token}: "
                f"{old_decision} → "
                f"{new_decision}"
            )
        )

    return summaries


# ==========================================================
# Telegram Delivery
# ==========================================================

def deliver_change_digest(
    *,
    changes: list[dict[str, object]],
    send_digest: Callable[
        ...,
        dict[str, object],
    ] = send_change_digest,
) -> dict[str, object]:
    """
    Attempt Telegram delivery without invalidating a completed
    market snapshot.

    Returns one of three statuses:

    SENT
        A meaningful digest was delivered.

    SKIPPED
        No meaningful changes required a Telegram message.

    FAILED
        Telegram configuration, network, or API delivery failed.
    """

    try:

        result = send_digest(
            changes=changes,
        )

    except Exception as error:

        return {
            "success": False,
            "sent": False,
            "status": "FAILED",
            "changes": len(
                changes,
            ),
            "error": str(
                error,
            ),
        }

    sent = (
        result.get(
            "sent",
            False,
        )
        is True
    )

    return {
        **result,
        "success": True,
        "sent": sent,
        "status": (
            "SENT"
            if sent
            else "SKIPPED"
        ),
        "error": None,
    }


# ==========================================================
# Automated Workflow
# ==========================================================

def execute_founder_scheduler(
    *,
    load_snapshot: Callable[
        [],
        dict[str, Any],
    ] = read_latest_snapshot,
    generate_snapshot: Callable[
        [],
        dict[str, object],
    ] = generate_latest_snapshot,
    detect_changes: Callable[
        ...,
        list[dict[str, object]],
    ] = detect_meaningful_changes,
    send_digest: Callable[
        ...,
        dict[str, object],
    ] = send_change_digest,
) -> dict[str, object]:
    """
    Execute one complete automated AlphaRadar run.

    Snapshot generation and change comparison errors propagate
    to the command-line wrapper.

    Telegram errors are captured as a degraded result because
    the newly generated snapshot remains valid.
    """

    previous_snapshot = load_previous_snapshot(
        load_snapshot=load_snapshot,
    )

    generation_result = generate_snapshot()

    current_snapshot = load_snapshot()

    changes = detect_changes(
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
    )

    if not isinstance(
        changes,
        list,
    ):

        raise RuntimeError(
            "Meaningful change detector returned invalid data."
        )

    telegram_result = deliver_change_digest(
        changes=changes,
        send_digest=send_digest,
    )

    telegram_status = str(
        telegram_result.get(
            "status",
            "FAILED",
        )
    ).strip().upper()

    automation_status = (
        "DEGRADED"
        if telegram_status == "FAILED"
        else "HEALTHY"
    )

    return {
        "success": True,
        "automation_status": automation_status,
        "baseline_created": (
            previous_snapshot is None
        ),
        "generated_at": current_snapshot.get(
            "generated_at",
            generation_result.get(
                "generated_at",
                "UNKNOWN",
            ),
        ),
        "total_coins": current_snapshot.get(
            "total_coins",
            generation_result.get(
                "total_coins",
                0,
            ),
        ),
        "available_coins": current_snapshot.get(
            "available_coins",
            generation_result.get(
                "available_coins",
                0,
            ),
        ),
        "unavailable_coins": current_snapshot.get(
            "unavailable_coins",
            generation_result.get(
                "unavailable_coins",
                0,
            ),
        ),
        "meaningful_changes": len(
            changes,
        ),
        "change_summaries": (
            build_change_summaries(
                changes,
            )
        ),
        "telegram_sent": (
            telegram_result.get(
                "sent",
                False,
            )
            is True
        ),
        "telegram_status": telegram_status,
        "telegram_error": telegram_result.get(
            "error",
        ),
        "snapshot_file": generation_result.get(
            "snapshot_file",
            "UNKNOWN",
        ),
    }


# ==========================================================
# Terminal Output
# ==========================================================

def print_heading() -> None:
    """
    Display the automation heading.
    """

    print()
    print("=" * CONSOLE_WIDTH)
    print("AlphaRadar Founder Automation")
    print("=" * CONSOLE_WIDTH)
    print()


def print_change_summary(
    result: dict[str, object],
) -> None:
    """
    Display concise meaningful-change information.
    """

    summaries = result.get(
        "change_summaries",
        [],
    )

    if not isinstance(
        summaries,
        list,
    ) or not summaries:

        return

    print()
    print("Market changes")
    print("-" * CONSOLE_WIDTH)

    for summary in summaries:

        print(
            f"• {summary}"
        )


def print_telegram_status(
    result: dict[str, object],
) -> None:
    """
    Display Telegram delivery status and warning details.
    """

    telegram_status = str(
        result.get(
            "telegram_status",
            "UNKNOWN",
        )
    ).strip().upper()

    print()
    print("Telegram")
    print("-" * CONSOLE_WIDTH)

    if telegram_status == "SENT":

        print(
            "Status             : SENT"
        )

        return

    if telegram_status == "SKIPPED":

        print(
            "Status             : SKIPPED"
        )

        print(
            "Reason             : "
            "No meaningful alert required"
        )

        return

    print(
        "Status             : FAILED"
    )

    telegram_error = result.get(
        "telegram_error",
    )

    if telegram_error:

        print(
            "Warning            : "
            f"{telegram_error}"
        )

    print(
        "Snapshot preserved : YES"
    )


def print_scheduler_result(
    result: dict[str, object],
) -> None:
    """
    Display one production-style automated-run result.
    """

    print_heading()

    print("Scan summary")
    print("-" * CONSOLE_WIDTH)

    print(
        "Generated at       : "
        f"{result.get('generated_at', 'UNKNOWN')}"
    )

    print(
        "Total coins        : "
        f"{result.get('total_coins', 0)}"
    )

    print(
        "Available coins    : "
        f"{result.get('available_coins', 0)}"
    )

    print(
        "Unavailable coins  : "
        f"{result.get('unavailable_coins', 0)}"
    )

    print(
        "Meaningful changes : "
        f"{result.get('meaningful_changes', 0)}"
    )

    print_change_summary(
        result,
    )

    print_telegram_status(
        result,
    )

    print()
    print("System health")
    print("-" * CONSOLE_WIDTH)

    print(
        "Radar              : ONLINE"
    )

    print(
        "Snapshot           : UPDATED"
    )

    print(
        "Automation status  : "
        f"{result.get('automation_status', 'UNKNOWN')}"
    )

    if result.get(
        "baseline_created",
        False,
    ):

        print()
        print(
            "Baseline created. "
            "Initial Telegram alert was suppressed."
        )

    print()
    print(
        "Snapshot file      : "
        f"{result.get('snapshot_file', 'UNKNOWN')}"
    )

    print()
    print("=" * CONSOLE_WIDTH)
    print("Automation completed")
    print("=" * CONSOLE_WIDTH)
    print()


def print_scheduler_failure(
    error: Exception,
) -> None:
    """
    Display a critical automation failure.
    """

    print_heading()

    print("Automation failed")
    print("-" * CONSOLE_WIDTH)

    print(
        str(
            error,
        )
    )

    print()
    print("System health")
    print("-" * CONSOLE_WIDTH)

    print(
        "Radar              : OFFLINE"
    )

    print(
        "Snapshot           : NOT CONFIRMED"
    )

    print(
        "Automation status  : FAILED"
    )

    print()


# ==========================================================
# Command Entry Point
# ==========================================================

def run_founder_scheduler(
    *,
    execute: Callable[
        [],
        dict[str, object],
    ] = execute_founder_scheduler,
) -> int:
    """
    Run one scheduler command and return an operating-system
    exit code.

    Exit code 0:
        Snapshot generation and comparison completed, including
        runs where Telegram delivery was degraded.

    Exit code 1:
        Snapshot generation, loading, or comparison failed.
    """

    try:

        result = execute()

    except Exception as error:

        print_scheduler_failure(
            error,
        )

        return 1

    print_scheduler_result(
        result,
    )

    return 0


def main() -> int:
    """
    Execute one AlphaRadar automated scan cycle.
    """

    return run_founder_scheduler()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )