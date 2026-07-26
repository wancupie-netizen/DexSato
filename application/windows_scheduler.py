"""
AlphaRadar Windows Scheduler Service.

Creates and removes the Windows Task Scheduler entries
required to run Founder Automation automatically.

Founder V1 installation flow
----------------------------
1. Build a machine-local command runner.
2. Register three daily Windows scheduled tasks.
3. Execute founder_scheduler.py from the project root.

Founder V1 uninstall flow
-------------------------
1. Delete the three AlphaRadar scheduled tasks.
2. Optionally remove the generated local runner.
3. Preserve configuration, snapshots, source code, and data.

The runner is written under:

    output/automation/run_founder_scheduler.cmd

The output directory is excluded from Git.

This module does NOT:
- run market scans directly
- store Telegram credentials
- modify the project .env file
- delete snapshots
- delete database records
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path


# ==========================================================
# Paths and Task Names
# ==========================================================

PROJECT_ROOT = Path(
    __file__,
).resolve().parent.parent


FOUNDER_SCHEDULER_FILE = (
    PROJECT_ROOT
    / "founder_scheduler.py"
)


AUTOMATION_OUTPUT_DIR = (
    PROJECT_ROOT
    / "output"
    / "automation"
)


RUNNER_FILE = (
    AUTOMATION_OUTPUT_DIR
    / "run_founder_scheduler.cmd"
)


TASK_NAMES = (
    "AlphaRadar Founder Scan 1",
    "AlphaRadar Founder Scan 2",
    "AlphaRadar Founder Scan 3",
)


# ==========================================================
# Platform Validation
# ==========================================================

def ensure_windows(
    *,
    platform_name: str = os.name,
) -> None:
    """
    Ensure Windows Task Scheduler is available.
    """

    if platform_name != "nt":

        raise RuntimeError(
            "AlphaRadar Windows Scheduler can only be "
            "managed on Windows."
        )


# ==========================================================
# Runner Generation
# ==========================================================

def quote_windows_path(
    path: Path | str,
) -> str:
    """
    Quote one Windows file-system path.
    """

    resolved = str(
        Path(
            path,
        ).resolve()
    )

    return f'"{resolved}"'


def build_runner_content(
    *,
    project_root: Path = PROJECT_ROOT,
    python_executable: Path | str = sys.executable,
    scheduler_file: Path = FOUNDER_SCHEDULER_FILE,
) -> str:
    """
    Build the machine-local Windows command runner.

    The runner changes into the project root before launching
    Python so all relative AlphaRadar paths remain correct.
    """

    resolved_project_root = Path(
        project_root,
    ).resolve()

    resolved_python = Path(
        python_executable,
    ).resolve()

    resolved_scheduler = Path(
        scheduler_file,
    ).resolve()

    return "\n".join(
        [
            "@echo off",
            "setlocal",
            (
                "cd /d "
                f'{quote_windows_path(resolved_project_root)}'
            ),
            (
                f"{quote_windows_path(resolved_python)} "
                f"{quote_windows_path(resolved_scheduler)}"
            ),
            (
                'set "ALPHARADAR_EXIT_CODE='
                '%ERRORLEVEL%"'
            ),
            (
                "endlocal & exit /b "
                "%ALPHARADAR_EXIT_CODE%"
            ),
            "",
        ]
    )


def write_runner_file(
    *,
    runner_file: Path = RUNNER_FILE,
    project_root: Path = PROJECT_ROOT,
    python_executable: Path | str = sys.executable,
    scheduler_file: Path = FOUNDER_SCHEDULER_FILE,
) -> Path:
    """
    Write the machine-local Founder Scheduler runner.
    """

    resolved_runner = Path(
        runner_file,
    ).resolve()

    resolved_scheduler = Path(
        scheduler_file,
    ).resolve()

    if not resolved_scheduler.is_file():

        raise FileNotFoundError(
            "AlphaRadar founder_scheduler.py was not found."
        )

    resolved_runner.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    resolved_runner.write_text(
        build_runner_content(
            project_root=project_root,
            python_executable=python_executable,
            scheduler_file=resolved_scheduler,
        ),
        encoding="utf-8",
        newline="\r\n",
    )

    return resolved_runner


# ==========================================================
# Task Definitions
# ==========================================================

def build_task_definitions(
    *,
    scan_times: Sequence[str],
    task_names: Sequence[str] = TASK_NAMES,
) -> list[dict[str, str]]:
    """
    Pair each configured scan time with one stable task name.
    """

    if len(
        scan_times,
    ) != len(
        task_names,
    ):

        raise ValueError(
            "AlphaRadar requires exactly three scan times."
        )

    definitions: list[
        dict[str, str]
    ] = []

    for task_name, scan_time in zip(
        task_names,
        scan_times,
        strict=True,
    ):

        definitions.append(
            {
                "task_name": str(
                    task_name,
                ),
                "scan_time": str(
                    scan_time,
                ),
            }
        )

    return definitions


def build_create_task_command(
    *,
    task_name: str,
    scan_time: str,
    runner_file: Path = RUNNER_FILE,
) -> list[str]:
    """
    Build one schtasks.exe daily task registration command.

    The /F option makes installation repeatable by replacing
    an existing AlphaRadar task with the same stable name.
    """

    resolved_runner = Path(
        runner_file,
    ).resolve()

    return [
        "schtasks.exe",
        "/Create",
        "/TN",
        task_name,
        "/TR",
        quote_windows_path(
            resolved_runner,
        ),
        "/SC",
        "DAILY",
        "/ST",
        scan_time,
        "/F",
    ]


def build_delete_task_command(
    *,
    task_name: str,
) -> list[str]:
    """
    Build one forced scheduled-task deletion command.
    """

    return [
        "schtasks.exe",
        "/Delete",
        "/TN",
        task_name,
        "/F",
    ]


# ==========================================================
# Windows Command Execution
# ==========================================================

def run_scheduler_command(
    command: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    """
    Execute one Windows Task Scheduler command.
    """

    return subprocess.run(
        list(
            command,
        ),
        capture_output=True,
        text=True,
        check=False,
    )


# ==========================================================
# Task Installation
# ==========================================================

def install_windows_tasks(
    *,
    scan_times: Sequence[str],
    runner_file: Path = RUNNER_FILE,
    task_names: Sequence[str] = TASK_NAMES,
    run_command: Callable[
        [
            Sequence[str],
        ],
        subprocess.CompletedProcess[str],
    ] = run_scheduler_command,
    platform_name: str = os.name,
) -> list[dict[str, object]]:
    """
    Register all AlphaRadar Founder V1 scheduled tasks.
    """

    ensure_windows(
        platform_name=platform_name,
    )

    definitions = build_task_definitions(
        scan_times=scan_times,
        task_names=task_names,
    )

    results: list[
        dict[str, object]
    ] = []

    for definition in definitions:

        task_name = definition[
            "task_name"
        ]

        scan_time = definition[
            "scan_time"
        ]

        command = build_create_task_command(
            task_name=task_name,
            scan_time=scan_time,
            runner_file=runner_file,
        )

        completed = run_command(
            command,
        )

        stdout = str(
            completed.stdout
            or ""
        ).strip()

        stderr = str(
            completed.stderr
            or ""
        ).strip()

        if completed.returncode != 0:

            detail = (
                stderr
                or stdout
                or "Unknown Windows Task Scheduler error."
            )

            raise RuntimeError(
                "Failed to register scheduled task "
                f"'{task_name}': {detail}"
            )

        results.append(
            {
                "success": True,
                "task_name": task_name,
                "scan_time": scan_time,
                "returncode": (
                    completed.returncode
                ),
                "message": stdout,
            }
        )

    return results


# ==========================================================
# Task Removal
# ==========================================================

def is_missing_task_message(
    message: object,
) -> bool:
    """
    Identify the standard Windows missing-task response.

    Windows may return localized wording, so the check also
    accepts the commonly returned ERROR level message.
    """

    normalized = str(
        message
        or ""
    ).strip().lower()

    missing_markers = (
        "cannot find the file specified",
        "system cannot find",
        "task does not exist",
        "scheduled task does not exist",
        "cannot find the task",
    )

    return any(
        marker in normalized
        for marker in missing_markers
    )


def remove_windows_tasks(
    *,
    task_names: Sequence[str] = TASK_NAMES,
    run_command: Callable[
        [
            Sequence[str],
        ],
        subprocess.CompletedProcess[str],
    ] = run_scheduler_command,
    platform_name: str = os.name,
    ignore_missing: bool = True,
) -> list[dict[str, object]]:
    """
    Remove all AlphaRadar Founder scheduled tasks.

    Re-running the uninstaller is safe. Missing tasks are
    reported as ALREADY REMOVED when ignore_missing=True.
    """

    ensure_windows(
        platform_name=platform_name,
    )

    results: list[
        dict[str, object]
    ] = []

    for task_name in task_names:

        command = build_delete_task_command(
            task_name=task_name,
        )

        completed = run_command(
            command,
        )

        stdout = str(
            completed.stdout
            or ""
        ).strip()

        stderr = str(
            completed.stderr
            or ""
        ).strip()

        detail = (
            stderr
            or stdout
            or ""
        )

        if completed.returncode == 0:

            results.append(
                {
                    "success": True,
                    "task_name": task_name,
                    "status": "REMOVED",
                    "returncode": 0,
                    "message": stdout,
                }
            )

            continue

        if (
            ignore_missing
            and is_missing_task_message(
                detail,
            )
        ):

            results.append(
                {
                    "success": True,
                    "task_name": task_name,
                    "status": "ALREADY REMOVED",
                    "returncode": (
                        completed.returncode
                    ),
                    "message": detail,
                }
            )

            continue

        raise RuntimeError(
            "Failed to remove scheduled task "
            f"'{task_name}': "
            f"{detail or 'Unknown Windows Task Scheduler error.'}"
        )

    return results


def remove_runner_file(
    *,
    runner_file: Path = RUNNER_FILE,
) -> dict[str, object]:
    """
    Remove the generated machine-local command runner.

    The automation directory is removed only when empty.
    """

    resolved_runner = Path(
        runner_file,
    ).resolve()

    if not resolved_runner.exists():

        return {
            "success": True,
            "removed": False,
            "status": "ALREADY REMOVED",
            "runner_file": str(
                resolved_runner,
            ),
        }

    if not resolved_runner.is_file():

        raise RuntimeError(
            "AlphaRadar automation runner path is not a file."
        )

    resolved_runner.unlink()

    parent_directory = (
        resolved_runner.parent
    )

    try:

        parent_directory.rmdir()

    except OSError:

        pass

    return {
        "success": True,
        "removed": True,
        "status": "REMOVED",
        "runner_file": str(
            resolved_runner,
        ),
    }