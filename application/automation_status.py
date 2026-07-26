"""
AlphaRadar Founder Automation Status.

Collects health information for the Founder V1 automation.

Status sources
--------------
1. Project environment configuration
2. Windows scheduled tasks
3. Latest stored market snapshot
4. Overall Founder Automation health

This module does NOT:
- print console output
- register scheduled tasks
- delete scheduled tasks
- run market scans
- send Telegram messages
- expose secret credential values
"""

from __future__ import annotations

import csv
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from application.environment_config import (
    DEFAULT_ENV_FILE,
    get_configuration_status,
    get_scan_times,
    load_environment,
)

from application.founder_snapshot_service import (
    LATEST_SNAPSHOT_FILE,
    read_latest_snapshot,
)

from application.windows_scheduler import (
    TASK_NAMES,
)


# ==========================================================
# Configuration
# ==========================================================

SNAPSHOT_FRESH_HOURS = 12

SUCCESSFUL_TASK_RESULT = 0

NEVER_RUN_TASK_RESULTS = frozenset(
    {
        267011,
    }
)


# ==========================================================
# Shared Helpers
# ==========================================================

def _normalize_text(
    value: object,
    *,
    fallback: str = "UNKNOWN",
) -> str:
    """
    Normalize one value into display-safe text.
    """

    text = str(
        value
        if value is not None
        else fallback
    ).strip()

    return text or fallback


def _normalize_task_name(
    task_name: object,
) -> str:
    """
    Normalize a Windows scheduled-task name.
    """

    normalized = _normalize_text(
        task_name,
    )

    return normalized.lstrip(
        "\\",
    )


def _parse_integer(
    value: object,
) -> int | None:
    """
    Parse one integer value safely.
    """

    try:

        return int(
            str(
                value,
            ).strip()
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


# ==========================================================
# Windows Task Query
# ==========================================================

def run_status_command(
    command: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    """
    Execute one Windows Task Scheduler status command.
    """

    return subprocess.run(
        list(
            command,
        ),
        capture_output=True,
        text=True,
        check=False,
    )


def build_task_query_command(
    *,
    task_name: str,
) -> list[str]:
    """
    Build one machine-readable schtasks query command.
    """

    return [
        "schtasks.exe",
        "/Query",
        "/TN",
        task_name,
        "/V",
        "/FO",
        "CSV",
        "/NH",
    ]


def parse_task_csv(
    csv_output: str,
) -> dict[str, str]:
    """
    Parse one schtasks CSV result.

    The Windows CSV output contains many localized columns.
    The service keeps the raw row indexed by known English
    column positions used by schtasks /V /FO CSV.
    """

    if not isinstance(
        csv_output,
        str,
    ) or not csv_output.strip():

        raise ValueError(
            "Windows Task Scheduler returned empty task data."
        )

    reader = csv.reader(
        StringIO(
            csv_output,
        )
    )

    rows = list(
        reader,
    )

    if not rows:

        raise ValueError(
            "Windows Task Scheduler returned invalid task data."
        )

    row = rows[
        0
    ]

    if len(
        row,
    ) < 9:

        raise ValueError(
            "Windows Task Scheduler task data is incomplete."
        )

    return {
        "host_name": row[0],
        "task_name": row[1],
        "next_run_time": row[2],
        "status": row[3],
        "logon_mode": row[4],
        "last_run_time": row[5],
        "last_result": row[6],
        "author": row[7],
        "task_to_run": row[8],
    }


def query_windows_task(
    *,
    task_name: str,
    run_command: Callable[
        [
            Sequence[str],
        ],
        subprocess.CompletedProcess[str],
    ] = run_status_command,
    platform_name: str = os.name,
) -> dict[str, object]:
    """
    Query one AlphaRadar Windows scheduled task.
    """

    if platform_name != "nt":

        return {
            "task_name": task_name,
            "installed": False,
            "status": "UNSUPPORTED",
            "ready": False,
            "next_run_time": None,
            "last_run_time": None,
            "last_result": None,
            "last_result_status": "UNKNOWN",
            "error": (
                "Windows Task Scheduler is unavailable "
                "on this operating system."
            ),
        }

    command = build_task_query_command(
        task_name=task_name,
    )

    completed = run_command(
        command,
    )

    stdout = _normalize_text(
        completed.stdout,
        fallback="",
    )

    stderr = _normalize_text(
        completed.stderr,
        fallback="",
    )

    if completed.returncode != 0:

        error = (
            stderr
            or stdout
            or "Scheduled task was not found."
        )

        return {
            "task_name": task_name,
            "installed": False,
            "status": "NOT INSTALLED",
            "ready": False,
            "next_run_time": None,
            "last_run_time": None,
            "last_result": None,
            "last_result_status": "UNKNOWN",
            "error": error,
        }

    parsed = parse_task_csv(
        stdout,
    )

    normalized_status = _normalize_text(
        parsed.get(
            "status",
        )
    ).upper()

    raw_last_result = _parse_integer(
        parsed.get(
            "last_result",
        )
    )

    if raw_last_result == SUCCESSFUL_TASK_RESULT:

        last_result_status = "SUCCESS"

    elif raw_last_result in NEVER_RUN_TASK_RESULTS:

        last_result_status = "NOT RUN YET"

    elif raw_last_result is None:

        last_result_status = "UNKNOWN"

    else:

        last_result_status = "FAILED"

    ready = normalized_status in {
        "READY",
        "RUNNING",
    }

    return {
        "task_name": _normalize_task_name(
            parsed.get(
                "task_name",
                task_name,
            )
        ),
        "installed": True,
        "status": normalized_status,
        "ready": ready,
        "next_run_time": _normalize_text(
            parsed.get(
                "next_run_time",
            ),
            fallback="UNKNOWN",
        ),
        "last_run_time": _normalize_text(
            parsed.get(
                "last_run_time",
            ),
            fallback="UNKNOWN",
        ),
        "last_result": raw_last_result,
        "last_result_status": last_result_status,
        "task_to_run": _normalize_text(
            parsed.get(
                "task_to_run",
            ),
            fallback="UNKNOWN",
        ),
        "logon_mode": _normalize_text(
            parsed.get(
                "logon_mode",
            ),
            fallback="UNKNOWN",
        ),
        "error": None,
    }


def collect_task_statuses(
    *,
    task_names: Sequence[str] = TASK_NAMES,
    scan_times: Sequence[str],
    query_task: Callable[
        ...,
        dict[str, object],
    ] = query_windows_task,
) -> list[dict[str, object]]:
    """
    Collect status for all Founder V1 scheduled tasks.
    """

    if len(
        task_names,
    ) != len(
        scan_times,
    ):

        raise ValueError(
            "Task names and scan times must have equal length."
        )

    results: list[
        dict[str, object]
    ] = []

    for task_name, scan_time in zip(
        task_names,
        scan_times,
        strict=True,
    ):

        task_status = query_task(
            task_name=task_name,
        )

        results.append(
            {
                **task_status,
                "configured_time": scan_time,
            }
        )

    return results


# ==========================================================
# Snapshot Health
# ==========================================================

def parse_snapshot_timestamp(
    value: object,
) -> datetime:
    """
    Parse one timezone-aware snapshot timestamp.
    """

    candidate = _normalize_text(
        value,
        fallback="",
    )

    try:

        parsed = datetime.fromisoformat(
            candidate.replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError as error:

        raise ValueError(
            "Latest snapshot timestamp is invalid."
        ) from error

    if parsed.tzinfo is None:

        raise ValueError(
            "Latest snapshot timestamp must be timezone-aware."
        )

    return parsed


def collect_snapshot_status(
    *,
    load_snapshot: Callable[
        [],
        dict[str, Any],
    ] = read_latest_snapshot,
    snapshot_file: Path = LATEST_SNAPSHOT_FILE,
    now: datetime | None = None,
    fresh_hours: int = SNAPSHOT_FRESH_HOURS,
) -> dict[str, object]:
    """
    Collect latest snapshot availability and freshness.
    """

    resolved_file = Path(
        snapshot_file,
    ).resolve()

    if not resolved_file.exists():

        return {
            "exists": False,
            "valid": False,
            "fresh": False,
            "status": "MISSING",
            "snapshot_file": str(
                resolved_file,
            ),
            "generated_at": None,
            "age_minutes": None,
            "total_coins": 0,
            "available_coins": 0,
            "error": (
                "Latest AlphaRadar snapshot is not available."
            ),
        }

    try:

        snapshot = load_snapshot()

        generated_at = parse_snapshot_timestamp(
            snapshot.get(
                "generated_at",
            )
        )

    except Exception as error:

        return {
            "exists": True,
            "valid": False,
            "fresh": False,
            "status": "INVALID",
            "snapshot_file": str(
                resolved_file,
            ),
            "generated_at": None,
            "age_minutes": None,
            "total_coins": 0,
            "available_coins": 0,
            "error": str(
                error,
            ),
        }

    resolved_now = (
        now
        or datetime.now(
            timezone.utc,
        )
    )

    if resolved_now.tzinfo is None:

        raise ValueError(
            "Current status time must be timezone-aware."
        )

    age_seconds = max(
        0.0,
        (
            resolved_now
            - generated_at.astimezone(
                resolved_now.tzinfo,
            )
        ).total_seconds(),
    )

    age_minutes = round(
        age_seconds
        / 60,
    )

    fresh = age_seconds <= (
        fresh_hours
        * 60
        * 60
    )

    return {
        "exists": True,
        "valid": True,
        "fresh": fresh,
        "status": (
            "FRESH"
            if fresh
            else "STALE"
        ),
        "snapshot_file": str(
            resolved_file,
        ),
        "generated_at": (
            generated_at.isoformat()
        ),
        "age_minutes": age_minutes,
        "total_coins": snapshot.get(
            "total_coins",
            0,
        ),
        "available_coins": snapshot.get(
            "available_coins",
            0,
        ),
        "error": None,
    }


# ==========================================================
# Overall Health
# ==========================================================

def determine_overall_health(
    *,
    configuration: Mapping[str, object],
    tasks: Sequence[Mapping[str, object]],
    snapshot: Mapping[str, object],
) -> str:
    """
    Determine Founder Automation overall health.
    """

    configuration_ready = (
        configuration.get(
            "ready",
            False,
        )
        is True
    )

    tasks_ready = bool(
        tasks,
    ) and all(
        task.get(
            "installed",
            False,
        )
        is True
        and task.get(
            "ready",
            False,
        )
        is True
        for task in tasks
    )

    snapshot_valid = (
        snapshot.get(
            "valid",
            False,
        )
        is True
    )

    snapshot_fresh = (
        snapshot.get(
            "fresh",
            False,
        )
        is True
    )

    if (
        configuration_ready
        and tasks_ready
        and snapshot_valid
        and snapshot_fresh
    ):

        return "HEALTHY"

    if (
        configuration_ready
        and snapshot_valid
    ):

        return "DEGRADED"

    return "FAILED"


def collect_automation_status(
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
    collect_tasks: Callable[
        ...,
        list[dict[str, object]],
    ] = collect_task_statuses,
    collect_snapshot: Callable[
        ...,
        dict[str, object],
    ] = collect_snapshot_status,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, object]:
    """
    Collect the complete Founder Automation health status.
    """

    load_result = load_config(
        env_file=env_file,
    )

    configuration = configuration_status(
        env_file=env_file,
    )

    scan_times = resolve_scan_times()

    tasks = collect_tasks(
        scan_times=scan_times,
    )

    snapshot = collect_snapshot()

    overall_health = determine_overall_health(
        configuration=configuration,
        tasks=tasks,
        snapshot=snapshot,
    )

    return {
        "success": True,
        "checked_at": datetime.now(
            timezone.utc,
        ).isoformat(),
        "environment_loaded": (
            load_result.get(
                "loaded",
                False,
            )
            is True
        ),
        "configuration": configuration,
        "tasks": tasks,
        "snapshot": snapshot,
        "overall_health": overall_health,
    }