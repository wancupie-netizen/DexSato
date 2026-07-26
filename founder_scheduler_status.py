"""
AlphaRadar Founder Scheduler Status.

Usage:

    python founder_scheduler_status.py

The command:

1. Loads Founder V1 environment configuration.
2. Queries the three Windows scheduled tasks.
3. Checks the latest AlphaRadar snapshot.
4. Determines overall automation health.
5. Prints one founder-friendly terminal report.
6. Returns an operating-system exit code.

Exit codes
----------
0
    AlphaRadar Founder is HEALTHY.

1
    AlphaRadar Founder is FAILED or the status check itself
    could not be completed.

2
    AlphaRadar Founder is DEGRADED and requires attention.

This module does NOT:
- register Windows scheduled tasks
- delete Windows scheduled tasks
- run a market scan
- send Telegram messages
- expose secret credential values
"""

from __future__ import annotations

from collections.abc import Callable

from application.automation_status import (
    collect_automation_status,
)

from presentation.automation_status_presenter import (
    print_automation_status,
)


# ==========================================================
# Exit Codes
# ==========================================================

HEALTHY_EXIT_CODE = 0

FAILED_EXIT_CODE = 1

DEGRADED_EXIT_CODE = 2


# ==========================================================
# Health Resolution
# ==========================================================

def resolve_health_exit_code(
    status: dict[str, object],
) -> int:
    """
    Convert overall Founder health into an operating-system
    exit code.
    """

    overall_health = str(
        status.get(
            "overall_health",
            "FAILED",
        )
    ).strip().upper()

    if overall_health == "HEALTHY":

        return HEALTHY_EXIT_CODE

    if overall_health == "DEGRADED":

        return DEGRADED_EXIT_CODE

    return FAILED_EXIT_CODE


# ==========================================================
# Failure Presentation
# ==========================================================

def print_status_failure(
    error: Exception,
) -> None:
    """
    Display a status-check failure.
    """

    print()
    print("=" * 60)
    print("AlphaRadar Founder Health")
    print("=" * 60)
    print()

    print("Health check failed")
    print("-" * 60)

    print(
        str(
            error,
        )
    )

    print()
    print("Overall Status")
    print("-" * 60)

    print(
        "Health                   "
        "✗ FAILED"
    )

    print(
        "AlphaRadar Founder status "
        "could not be determined."
    )

    print()
    print("=" * 60)
    print()


# ==========================================================
# Status Workflow
# ==========================================================

def execute_founder_status(
    *,
    collect_status: Callable[
        ...,
        dict[str, object],
    ] = collect_automation_status,
) -> dict[str, object]:
    """
    Collect and validate the Founder Automation status.
    """

    status = collect_status()

    if not isinstance(
        status,
        dict,
    ):

        raise RuntimeError(
            "Founder Automation status returned invalid data."
        )

    if status.get(
        "success",
        False,
    ) is not True:

        raise RuntimeError(
            "Founder Automation health check was unsuccessful."
        )

    return status


def run_founder_status(
    *,
    execute: Callable[
        [],
        dict[str, object],
    ] = execute_founder_status,
    present: Callable[
        [
            dict[str, object],
        ],
        None,
    ] = print_automation_status,
) -> int:
    """
    Run one Founder Automation health check.

    The report is always printed when status collection
    succeeds, including DEGRADED and FAILED system states.
    """

    try:

        status = execute()

    except Exception as error:

        print_status_failure(
            error,
        )

        return FAILED_EXIT_CODE

    present(
        status,
    )

    return resolve_health_exit_code(
        status,
    )


# ==========================================================
# Command Entry Point
# ==========================================================

def main() -> int:
    """
    Execute one AlphaRadar Founder health check.
    """

    return run_founder_status()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )