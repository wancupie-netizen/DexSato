"""
DexSato Windows Scheduler Installer.

Usage:

    python install_scheduler.py

The installer:

1. Loads the project .env file.
2. Validates required Founder configuration.
3. Reads the configured daily scan times.
4. Creates a machine-local command runner.
5. Registers three Windows scheduled tasks.

Re-running this installer safely replaces the existing
DexSato tasks with the current configuration.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from application.environment_config import (
    get_configuration_status,
    get_scan_times,
    load_environment,
)

from application.windows_scheduler import (
    PROJECT_ROOT,
    RUNNER_FILE,
    install_windows_tasks,
    write_runner_file,
)


# ==========================================================
# Display
# ==========================================================

CONSOLE_WIDTH = 60


def print_heading() -> None:
    """
    Display the installer heading.
    """

    print()
    print("=" * CONSOLE_WIDTH)
    print("DexSato Windows Scheduler Installer")
    print("=" * CONSOLE_WIDTH)
    print()


def print_success(
    result: dict[str, object],
) -> None:
    """
    Display successful installation information.
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

            print(
                f"{task.get('scan_time', 'UNKNOWN'):<8}"
                f"{task.get('task_name', 'UNKNOWN')}"
            )

    print()
    print(
        "Runner file        : "
        f"{result.get('runner_file', 'UNKNOWN')}"
    )

    print(
        "Project root       : "
        f"{result.get('project_root', 'UNKNOWN')}"
    )

    print()
    print("Installation completed.")
    print()


def print_failure(
    error: Exception,
) -> None:
    """
    Display installation failure information.
    """

    print("Installation failed")
    print("-" * CONSOLE_WIDTH)

    print(
        str(
            error,
        )
    )

    print()


# ==========================================================
# Installer Workflow
# ==========================================================

def execute_scheduler_installation(
    *,
    load_config: Callable[
        ...,
        dict[str, object],
    ] = load_environment,
    configuration_status: Callable[
        ...,
        dict[str, object],
    ] = get_configuration_status,
    resolve_scan_times: Callable[
        ...,
        tuple[str, ...],
    ] = get_scan_times,
    create_runner: Callable[
        ...,
        Path,
    ] = write_runner_file,
    install_tasks: Callable[
        ...,
        list[dict[str, object]],
    ] = install_windows_tasks,
    python_executable: str = sys.executable,
) -> dict[str, object]:
    """
    Execute the complete Windows Scheduler installation.
    """

    load_result = load_config()

    status = configuration_status()

    if status.get(
        "env_file_exists",
        False,
    ) is not True:

        raise RuntimeError(
            "DexSato .env file was not found. "
            "Create it from .env.example first."
        )

    if status.get(
        "ready",
        False,
    ) is not True:

        raise RuntimeError(
            "Telegram configuration is incomplete. "
            "Configure TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID in .env."
        )

    scan_times = resolve_scan_times()

    runner_file = create_runner(
        python_executable=python_executable,
    )

    tasks = install_tasks(
        scan_times=scan_times,
        runner_file=runner_file,
    )

    return {
        "success": True,
        "configuration_loaded": (
            load_result.get(
                "loaded",
                False,
            )
            is True
        ),
        "project_root": str(
            PROJECT_ROOT,
        ),
        "runner_file": str(
            runner_file,
        ),
        "scan_times": scan_times,
        "tasks": tasks,
    }


def run_scheduler_installer(
    *,
    execute: Callable[
        [],
        dict[str, object],
    ] = execute_scheduler_installation,
) -> int:
    """
    Run the installer and return an operating-system exit code.
    """

    print_heading()

    try:

        result = execute()

    except Exception as error:

        print_failure(
            error,
        )

        return 1

    print_success(
        result,
    )

    return 0


def main() -> int:
    """
    Install DexSato Windows scheduled tasks.
    """

    return run_scheduler_installer()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )