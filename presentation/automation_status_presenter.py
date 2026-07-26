"""
AlphaRadar Founder Automation Status Presenter.

Formats the Founder V1 automation health status for terminal
display.

Presentation sections
---------------------
1. Environment configuration
2. Windows scheduled tasks
3. Latest snapshot
4. System readiness
5. Overall health

This module does NOT:
- query Windows Task Scheduler
- read the project .env file
- read snapshot files
- register or delete scheduled tasks
- run market scans
- expose secret credential values
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


# ==========================================================
# Display Configuration
# ==========================================================

CONSOLE_WIDTH = 60

LABEL_WIDTH = 25


STATUS_SYMBOLS = {
    "HEALTHY": "✓",
    "READY": "✓",
    "CONFIGURED": "✓",
    "FOUND": "✓",
    "FRESH": "✓",
    "SUCCESS": "✓",
    "RUNNING": "✓",
    "DEGRADED": "!",
    "SKIPPED": "○",
    "NOT CONFIGURED": "○",
    "NOT RUN YET": "○",
    "UNKNOWN": "?",
    "FAILED": "✗",
    "MISSING": "✗",
    "INVALID": "✗",
    "STALE": "!",
    "NOT INSTALLED": "✗",
    "UNSUPPORTED": "✗",
}


OVERALL_MESSAGES = {
    "HEALTHY": (
        "AlphaRadar Founder is healthy."
    ),
    "DEGRADED": (
        "AlphaRadar Founder is running with warnings."
    ),
    "FAILED": (
        "AlphaRadar Founder requires attention."
    ),
}


# ==========================================================
# Shared Formatting
# ==========================================================

def _normalize_text(
    value: object,
    *,
    fallback: str = "UNKNOWN",
) -> str:
    """
    Normalize one value into terminal-safe text.
    """

    text = str(
        value
        if value is not None
        else fallback
    ).strip()

    return text or fallback


def _normalize_status(
    value: object,
) -> str:
    """
    Normalize one status value.
    """

    return _normalize_text(
        value,
    ).upper()


def status_symbol(
    status: object,
) -> str:
    """
    Return the terminal symbol for one status.
    """

    normalized = _normalize_status(
        status,
    )

    return STATUS_SYMBOLS.get(
        normalized,
        "?",
    )


def format_status(
    status: object,
) -> str:
    """
    Format one status with its terminal symbol.
    """

    normalized = _normalize_status(
        status,
    )

    return (
        f"{status_symbol(normalized)} "
        f"{normalized}"
    )


def format_boolean_status(
    value: object,
    *,
    true_label: str,
    false_label: str,
) -> str:
    """
    Convert one Boolean value into a labelled status.
    """

    if value is True:

        return format_status(
            true_label,
        )

    return format_status(
        false_label,
    )


def format_line(
    label: object,
    value: object,
) -> str:
    """
    Build one aligned terminal line.
    """

    normalized_label = _normalize_text(
        label,
    )

    normalized_value = _normalize_text(
        value,
    )

    return (
        f"{normalized_label:<{LABEL_WIDTH}}"
        f"{normalized_value}"
    )


def format_section_heading(
    title: object,
) -> list[str]:
    """
    Build one section heading.
    """

    return [
        _normalize_text(
            title,
        ),
        "-" * CONSOLE_WIDTH,
    ]


def format_iso_timestamp(
    value: object,
) -> str:
    """
    Format one ISO timestamp for terminal display.

    The timezone information is preserved.
    """

    candidate = _normalize_text(
        value,
        fallback="",
    )

    if not candidate:

        return "UNKNOWN"

    try:

        parsed = datetime.fromisoformat(
            candidate.replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError:

        return candidate

    return parsed.strftime(
        "%Y-%m-%d %H:%M:%S %z",
    )


def format_snapshot_age(
    value: object,
) -> str:
    """
    Format snapshot age from minutes into readable text.
    """

    try:

        minutes = int(
            value,
        )

    except (
        TypeError,
        ValueError,
    ):

        return "UNKNOWN"

    if minutes < 0:

        minutes = 0

    if minutes == 0:

        return "Less than 1 minute"

    if minutes == 1:

        return "1 minute"

    if minutes < 60:

        return f"{minutes} minutes"

    hours, remaining_minutes = divmod(
        minutes,
        60,
    )

    if hours == 1:

        hour_label = "1 hour"

    else:

        hour_label = f"{hours} hours"

    if remaining_minutes == 0:

        return hour_label

    if remaining_minutes == 1:

        minute_label = "1 minute"

    else:

        minute_label = (
            f"{remaining_minutes} minutes"
        )

    return (
        f"{hour_label} "
        f"{minute_label}"
    )


def short_task_name(
    task_name: object,
) -> str:
    """
    Build a concise scheduled-task display name.
    """

    normalized = _normalize_text(
        task_name,
    ).lstrip(
        "\\",
    )

    prefix = "AlphaRadar Founder "

    if normalized.startswith(
        prefix,
    ):

        return normalized[
            len(
                prefix,
            ):
        ]

    return normalized


# ==========================================================
# Environment Section
# ==========================================================

def build_environment_lines(
    configuration: dict[str, object],
) -> list[str]:
    """
    Build the environment-configuration section.
    """

    lines = format_section_heading(
        "Environment",
    )

    lines.extend(
        [
            format_line(
                ".env",
                format_boolean_status(
                    configuration.get(
                        "env_file_exists",
                        False,
                    ),
                    true_label="FOUND",
                    false_label="MISSING",
                ),
            ),
            format_line(
                "Telegram Bot",
                format_boolean_status(
                    configuration.get(
                        "telegram_bot_token_configured",
                        False,
                    ),
                    true_label="CONFIGURED",
                    false_label="NOT CONFIGURED",
                ),
            ),
            format_line(
                "Telegram Chat",
                format_boolean_status(
                    configuration.get(
                        "telegram_chat_id_configured",
                        False,
                    ),
                    true_label="CONFIGURED",
                    false_label="NOT CONFIGURED",
                ),
            ),
            format_line(
                "Public Dashboard",
                format_boolean_status(
                    configuration.get(
                        "public_dashboard_url_configured",
                        False,
                    ),
                    true_label="CONFIGURED",
                    false_label="NOT CONFIGURED",
                ),
            ),
            format_line(
                "Configuration",
                format_boolean_status(
                    configuration.get(
                        "ready",
                        False,
                    ),
                    true_label="READY",
                    false_label="FAILED",
                ),
            ),
        ]
    )

    return lines


# ==========================================================
# Scheduled Task Section
# ==========================================================

def format_task_last_result(
    task: dict[str, object],
) -> str:
    """
    Format one scheduled task's last result.
    """

    status = _normalize_status(
        task.get(
            "last_result_status",
            "UNKNOWN",
        )
    )

    raw_result = task.get(
        "last_result",
    )

    if raw_result is None:

        return format_status(
            status,
        )

    return (
        f"{format_status(status)} "
        f"({raw_result})"
    )


def build_task_lines(
    tasks: list[dict[str, object]],
) -> list[str]:
    """
    Build the Windows scheduled-task section.
    """

    lines = format_section_heading(
        "Automation",
    )

    if not tasks:

        lines.append(
            format_line(
                "Scheduled Tasks",
                format_status(
                    "NOT INSTALLED",
                ),
            )
        )

        return lines

    for task in tasks:

        configured_time = _normalize_text(
            task.get(
                "configured_time",
                "UNKNOWN",
            )
        )

        task_name = short_task_name(
            task.get(
                "task_name",
                "UNKNOWN",
            )
        )

        task_status = _normalize_status(
            task.get(
                "status",
                "UNKNOWN",
            )
        )

        if task.get(
            "installed",
            False,
        ) is not True:

            task_status = "NOT INSTALLED"

        lines.append(
            format_line(
                configured_time,
                (
                    f"{task_name} "
                    f"{format_status(task_status)}"
                ),
            )
        )

        next_run_time = task.get(
            "next_run_time",
        )

        if next_run_time:

            lines.append(
                format_line(
                    "  Next Run",
                    next_run_time,
                )
            )

        last_run_time = task.get(
            "last_run_time",
        )

        if last_run_time:

            lines.append(
                format_line(
                    "  Last Run",
                    last_run_time,
                )
            )

        lines.append(
            format_line(
                "  Last Result",
                format_task_last_result(
                    task,
                ),
            )
        )

        error = task.get(
            "error",
        )

        if error:

            lines.append(
                format_line(
                    "  Warning",
                    error,
                )
            )

    return lines


# ==========================================================
# Snapshot Section
# ==========================================================

def build_snapshot_lines(
    snapshot: dict[str, object],
) -> list[str]:
    """
    Build the latest-snapshot health section.
    """

    lines = format_section_heading(
        "Latest Snapshot",
    )

    snapshot_status = _normalize_status(
        snapshot.get(
            "status",
            "UNKNOWN",
        )
    )

    lines.append(
        format_line(
            "Status",
            format_status(
                snapshot_status,
            ),
        )
    )

    if snapshot.get(
        "exists",
        False,
    ) is not True:

        error = snapshot.get(
            "error",
        )

        if error:

            lines.append(
                format_line(
                    "Warning",
                    error,
                )
            )

        lines.append(
            format_line(
                "Snapshot File",
                snapshot.get(
                    "snapshot_file",
                    "UNKNOWN",
                ),
            )
        )

        return lines

    generated_at = snapshot.get(
        "generated_at",
    )

    if generated_at:

        lines.append(
            format_line(
                "Generated",
                format_iso_timestamp(
                    generated_at,
                ),
            )
        )

    lines.append(
        format_line(
            "Age",
            format_snapshot_age(
                snapshot.get(
                    "age_minutes",
                )
            ),
        )
    )

    lines.append(
        format_line(
            "Total Coins",
            snapshot.get(
                "total_coins",
                0,
            ),
        )
    )

    lines.append(
        format_line(
            "Available Coins",
            snapshot.get(
                "available_coins",
                0,
            ),
        )
    )

    lines.append(
        format_line(
            "Snapshot File",
            snapshot.get(
                "snapshot_file",
                "UNKNOWN",
            ),
        )
    )

    error = snapshot.get(
        "error",
    )

    if error:

        lines.append(
            format_line(
                "Warning",
                error,
            )
        )

    return lines


# ==========================================================
# System Readiness Section
# ==========================================================

def build_system_lines(
    status: dict[str, object],
) -> list[str]:
    """
    Build the high-level system-readiness section.
    """

    configuration = status.get(
        "configuration",
        {},
    )

    tasks = status.get(
        "tasks",
        [],
    )

    snapshot = status.get(
        "snapshot",
        {},
    )

    configuration_ready = (
        isinstance(
            configuration,
            dict,
        )
        and configuration.get(
            "ready",
            False,
        )
        is True
    )

    tasks_ready = (
        isinstance(
            tasks,
            list,
        )
        and bool(
            tasks,
        )
        and all(
            isinstance(
                task,
                dict,
            )
            and task.get(
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
    )

    snapshot_ready = (
        isinstance(
            snapshot,
            dict,
        )
        and snapshot.get(
            "valid",
            False,
        )
        is True
    )

    snapshot_fresh = (
        isinstance(
            snapshot,
            dict,
        )
        and snapshot.get(
            "fresh",
            False,
        )
        is True
    )

    lines = format_section_heading(
        "System",
    )

    lines.extend(
        [
            format_line(
                "Configuration",
                format_boolean_status(
                    configuration_ready,
                    true_label="READY",
                    false_label="FAILED",
                ),
            ),
            format_line(
                "Scheduled Tasks",
                format_boolean_status(
                    tasks_ready,
                    true_label="READY",
                    false_label="FAILED",
                ),
            ),
            format_line(
                "Snapshot",
                format_boolean_status(
                    snapshot_ready,
                    true_label="READY",
                    false_label="FAILED",
                ),
            ),
            format_line(
                "Snapshot Freshness",
                format_boolean_status(
                    snapshot_fresh,
                    true_label="FRESH",
                    false_label="STALE",
                ),
            ),
            format_line(
                "Telegram",
                format_boolean_status(
                    configuration_ready,
                    true_label="READY",
                    false_label="FAILED",
                ),
            ),
        ]
    )

    return lines


# ==========================================================
# Overall Health Section
# ==========================================================

def build_overall_health_lines(
    status: dict[str, object],
) -> list[str]:
    """
    Build the overall Founder Automation health section.
    """

    overall_health = _normalize_status(
        status.get(
            "overall_health",
            "UNKNOWN",
        )
    )

    message = OVERALL_MESSAGES.get(
        overall_health,
        (
            "AlphaRadar Founder health "
            "could not be determined."
        ),
    )

    lines = format_section_heading(
        "Overall Status",
    )

    lines.extend(
        [
            format_line(
                "Health",
                format_status(
                    overall_health,
                ),
            ),
            message,
        ]
    )

    return lines


# ==========================================================
# Complete Presenter
# ==========================================================

def build_automation_status_lines(
    status: dict[str, object],
) -> list[str]:
    """
    Build the complete Founder Automation health report.
    """

    if not isinstance(
        status,
        dict,
    ):

        raise ValueError(
            "Automation status must be a dictionary."
        )

    configuration = status.get(
        "configuration",
        {},
    )

    tasks = status.get(
        "tasks",
        [],
    )

    snapshot = status.get(
        "snapshot",
        {},
    )

    if not isinstance(
        configuration,
        dict,
    ):

        raise ValueError(
            "Automation configuration status is invalid."
        )

    if not isinstance(
        tasks,
        list,
    ):

        raise ValueError(
            "Automation task status is invalid."
        )

    if not isinstance(
        snapshot,
        dict,
    ):

        raise ValueError(
            "Automation snapshot status is invalid."
        )

    lines = [
        "",
        "=" * CONSOLE_WIDTH,
        "AlphaRadar Founder Health",
        "=" * CONSOLE_WIDTH,
        "",
    ]

    sections = [
        build_environment_lines(
            configuration,
        ),
        build_task_lines(
            tasks,
        ),
        build_snapshot_lines(
            snapshot,
        ),
        build_system_lines(
            status,
        ),
        build_overall_health_lines(
            status,
        ),
    ]

    for index, section in enumerate(
        sections,
    ):

        if index > 0:

            lines.append(
                "",
            )

        lines.extend(
            section,
        )

    checked_at = status.get(
        "checked_at",
    )

    if checked_at:

        lines.extend(
            [
                "",
                format_line(
                    "Checked At",
                    format_iso_timestamp(
                        checked_at,
                    ),
                ),
            ]
        )

    lines.extend(
        [
            "",
            "=" * CONSOLE_WIDTH,
            "",
        ]
    )

    return lines


def build_automation_status_text(
    status: dict[str, object],
) -> str:
    """
    Build the complete Founder Automation report as text.
    """

    return "\n".join(
        build_automation_status_lines(
            status,
        )
    )


def print_automation_status(
    status: dict[str, object],
) -> None:
    """
    Print the complete Founder Automation health report.
    """

    print(
        build_automation_status_text(
            status,
        )
    )