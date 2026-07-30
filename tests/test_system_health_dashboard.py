"""Tests for the Founder system-health dashboard data."""

import json

import pytest

from application.system_health_dashboard import (
    collect_system_dashboard_status,
    read_latest_run,
    write_latest_run,
)


def test_should_write_and_read_latest_run(tmp_path):
    """Completed automation results should survive process exit."""

    output_file = tmp_path / "latest_run.json"

    written_file = write_latest_run(
        {
            "automation_status": "HEALTHY",
            "telegram_status": "SENT",
            "meaningful_changes": 2,
        },
        output_file=output_file,
    )

    assert written_file == output_file

    payload = read_latest_run(
        input_file=output_file,
    )

    assert payload is not None
    assert payload["automation_status"] == "HEALTHY"
    assert payload["telegram_status"] == "SENT"
    assert payload["meaningful_changes"] == 2
    assert "recorded_at" in payload


def test_should_return_none_before_first_run(tmp_path):
    """A missing run record is a valid initial state."""

    assert read_latest_run(
        input_file=tmp_path / "missing.json",
    ) is None


def test_should_reject_invalid_run_record(tmp_path):
    """Malformed state must not be presented as healthy."""

    input_file = tmp_path / "latest_run.json"
    input_file.write_text(
        json.dumps(["invalid"]),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="run record is invalid",
    ):
        read_latest_run(
            input_file=input_file,
        )


def test_should_combine_health_and_latest_run():
    """The API model should combine all health sources."""

    result = collect_system_dashboard_status(
        collect_health=lambda: {
            "overall_health": "HEALTHY",
            "snapshot": {
                "status": "FRESH",
            },
            "tasks": [],
        },
        load_latest_run=lambda: {
            "telegram_status": "SKIPPED",
        },
    )

    assert result["overall_health"] == "HEALTHY"
    assert result["latest_run"] == {
        "telegram_status": "SKIPPED",
    }
    assert result["latest_run_error"] is None
