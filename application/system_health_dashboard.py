"""Read and persist data used by the Founder system-health dashboard."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from application.automation_status import collect_automation_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_OUTPUT_DIR = PROJECT_ROOT / "output" / "automation"
LATEST_RUN_FILE = AUTOMATION_OUTPUT_DIR / "latest_run.json"


def write_latest_run(
    result: dict[str, object],
    *,
    output_file: Path = LATEST_RUN_FILE,
) -> Path:
    """Atomically persist the latest completed automation result."""

    if not isinstance(result, dict):
        raise ValueError("Automation result must be a dictionary.")

    payload = {
        **result,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    resolved_file = Path(output_file)
    resolved_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = resolved_file.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary_file.replace(resolved_file)

    return resolved_file


def read_latest_run(
    *,
    input_file: Path = LATEST_RUN_FILE,
) -> dict[str, Any] | None:
    """Return the latest run record, or ``None`` before the first run."""

    resolved_file = Path(input_file)

    if not resolved_file.exists():
        return None

    try:
        payload = json.loads(resolved_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Latest automation run record is invalid.") from error

    if not isinstance(payload, dict):
        raise RuntimeError("Latest automation run record is invalid.")

    return payload


def collect_system_dashboard_status(
    *,
    collect_health: Callable[[], dict[str, object]] = collect_automation_status,
    load_latest_run: Callable[[], dict[str, Any] | None] = read_latest_run,
) -> dict[str, object]:
    """Combine scheduler, snapshot, configuration and last-run information."""

    health = collect_health()

    try:
        latest_run = load_latest_run()
        latest_run_error = None
    except RuntimeError as error:
        latest_run = None
        latest_run_error = str(error)

    return {
        **health,
        "latest_run": latest_run,
        "latest_run_error": latest_run_error,
    }
