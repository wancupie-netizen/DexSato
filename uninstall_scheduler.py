"""
AlphaRadar Windows Scheduler Uninstaller.

Usage:

    python uninstall_scheduler.py

The uninstaller:

1. Removes the three AlphaRadar scheduled tasks.
2. Removes the generated machine-local command runner.
3. Preserves .env configuration.
4. Preserves snapshots and AlphaRadar data.
5. Preserves all source code.

The command is safe to run more than once.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from application.windows_scheduler import (
    RUNNER_FILE,
    remove_runner_file,
    remove_windows_tasks,
)


# ==========================================================
# Display Configuration
# ==========================================================

CONSOLE_WIDTH = 60


# ==========================================================
# Presentation
# ==========================================================

def print_heading() -> None:
    """
    Display the uninstaller heading.
    """

    print()
    print("=" * CONSOLE_WIDTH)
    print("AlphaRadar Windows Scheduler Uninstaller")
    print("=" * CONSOLE_WIDTH)
    print()


def print_uninstall_result(
    result: dict[str, object],
) -> None:
    """
    Display successful task-removal information.
    """

    print("Scheduled tasks")
    print("-" * CONSOLE_WIDTH)

    tasks = result.get(
        "tasks",
        [],
    )

    if isinstance(
        tasks,
        list,
    ):

        for task in tasks:

            if not isinstance(
                task,
                dict,
            ):

                continue

            task_name = task.get(
                "task_name",
                "UNKNOWN",
            )

            status = task.get(
                "status",
                "UNKNOWN",
            )

            print(
                f"{task_name:<38}"
                f"{status}"
            )

    print()
    print("Local runner")
    print("-" * CONSOLE_WIDTH)

    runner = result.get(
        "runner",
        {},
    )

    if isinstance(
        runner,
        dict,
    ):

        print(
            "Status             : "
            f"{runner.get('status', 'UNKNOWN')}"
        )

        print(
            "Runner file        : "
            f"{runner.get('runner_file', 'UNKNOWN')}"
        )

    print()
    print("Preserved data")
    print("-" * CONSOLE_WIDTH)

    print(
        ".env configuration : PRESERVED"
    )

    print(
        "Snapshots          : PRESERVED"
    )

    print(
        "Source code        : PRESERVED"
    )

    print()
    print("=" * CONSOLE_WIDTH)
    print("Automation removed successfully")
    print("=" * CONSOLE_WIDTH)
    print()


def print_uninstall_failure(
    error: Exception,
) -> None:
    """
    Display an uninstall failure.
    """

    print("Uninstall failed")
    print("-" * CONSOLE_WIDTH)

    print(
        str(
            error,
        )
    )

    print()


# ==========================================================
# Uninstall Workflow
# ==========================================================

def execute_scheduler_uninstall(
    *,
    remove_tasks: Callable[
        ...,
        list[dict[str, object]],
    ] = remove_windows_tasks,
    remove_runner: Callable[
        ...,
        dict[str, object],
    ] = remove_runner_file,
    runner_file: Path = RUNNER_FILE,
) -> dict[str, object]:
    """
    Execute the complete Founder Scheduler uninstall.
    """

    task_results = remove_tasks()

    runner_result = remove_runner(
        runner_file=runner_file,
    )

    return {
        "success": True,
        "tasks": task_results,
        "runner": runner_result,
        "configuration_preserved": True,
        "snapshots_preserved": True,
        "source_code_preserved": True,
    }


def run_scheduler_uninstaller(
    *,
    execute: Callable[
        [],
        dict[str, object],
    ] = execute_scheduler_uninstall,
) -> int:
    """
    Run the uninstaller and return an operating-system exit
    code.
    """

    print_heading()

    try:

        result = execute()

    except Exception as error:

        print_uninstall_failure(
            error,
        )

        return 1

    print_uninstall_result(
        result,
    )

    return 0


def main() -> int:
    """
    Remove AlphaRadar Windows scheduled tasks.
    """

    return run_scheduler_uninstaller()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )