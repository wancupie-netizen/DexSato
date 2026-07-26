"""
Tests for AlphaRadar Windows Scheduler Uninstall.
"""

import subprocess

import pytest

from application.windows_scheduler import (
    TASK_NAMES,
    build_delete_task_command,
    is_missing_task_message,
    remove_runner_file,
    remove_windows_tasks,
)

from uninstall_scheduler import (
    execute_scheduler_uninstall,
    run_scheduler_uninstaller,
)


# ==========================================================
# Delete Command
# ==========================================================

def test_should_build_delete_task_command():
    """
    One task deletion should use forced schtasks removal.
    """

    result = build_delete_task_command(
        task_name="AlphaRadar Founder Scan 1",
    )

    assert result == [
        "schtasks.exe",
        "/Delete",
        "/TN",
        "AlphaRadar Founder Scan 1",
        "/F",
    ]


# ==========================================================
# Missing Task Detection
# ==========================================================

@pytest.mark.parametrize(
    "message",
    [
        (
            "ERROR: The system cannot find "
            "the file specified."
        ),
        (
            "The scheduled task does not exist."
        ),
        (
            "Cannot find the task."
        ),
    ],
)
def test_should_identify_missing_task_message(
    message,
):
    """
    Common missing-task responses should be recognized.
    """

    assert is_missing_task_message(
        message,
    ) is True


def test_should_not_treat_access_error_as_missing():
    """
    Permission errors must remain real uninstall failures.
    """

    assert is_missing_task_message(
        "ERROR: Access is denied.",
    ) is False


# ==========================================================
# Task Removal
# ==========================================================

def test_should_remove_all_windows_tasks():
    """
    Successful schtasks deletions should remove all tasks.
    """

    commands: list[
        list[str]
    ] = []

    def fake_run(
        command,
    ):

        commands.append(
            list(
                command,
            )
        )

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="SUCCESS: The scheduled task was deleted.",
            stderr="",
        )

    result = remove_windows_tasks(
        run_command=fake_run,
        platform_name="nt",
    )

    assert len(
        commands,
    ) == 3

    assert len(
        result,
    ) == 3

    assert result[0] == {
        "success": True,
        "task_name": TASK_NAMES[0],
        "status": "REMOVED",
        "returncode": 0,
        "message": (
            "SUCCESS: The scheduled task "
            "was deleted."
        ),
    }


def test_should_accept_tasks_already_removed():
    """
    Repeated uninstall should remain successful.
    """

    def missing_run(
        command,
    ):

        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr=(
                "ERROR: The system cannot find "
                "the file specified."
            ),
        )

    result = remove_windows_tasks(
        run_command=missing_run,
        platform_name="nt",
    )

    assert len(
        result,
    ) == 3

    assert all(
        item["success"] is True
        for item in result
    )

    assert all(
        item["status"] == "ALREADY REMOVED"
        for item in result
    )


def test_should_fail_on_real_task_removal_error():
    """
    Access errors should stop the uninstall.
    """

    def failing_run(
        command,
    ):

        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="ERROR: Access is denied.",
        )

    with pytest.raises(
        RuntimeError,
        match="Access is denied",
    ):

        remove_windows_tasks(
            run_command=failing_run,
            platform_name="nt",
        )


def test_should_reject_non_windows_removal():
    """
    Task removal must remain Windows-only.
    """

    with pytest.raises(
        RuntimeError,
        match="can only be managed on Windows",
    ):

        remove_windows_tasks(
            platform_name="posix",
        )


# ==========================================================
# Runner Removal
# ==========================================================

def test_should_remove_existing_runner_file(
    tmp_path,
):
    """
    Existing automation runner should be deleted.
    """

    automation_dir = (
        tmp_path
        / "output"
        / "automation"
    )

    automation_dir.mkdir(
        parents=True,
    )

    runner_file = (
        automation_dir
        / "run_founder_scheduler.cmd"
    )

    runner_file.write_text(
        "@echo off\n",
        encoding="utf-8",
    )

    result = remove_runner_file(
        runner_file=runner_file,
    )

    assert result == {
        "success": True,
        "removed": True,
        "status": "REMOVED",
        "runner_file": str(
            runner_file.resolve()
        ),
    }

    assert runner_file.exists() is False

    assert automation_dir.exists() is False


def test_should_accept_missing_runner_file(
    tmp_path,
):
    """
    Repeated uninstall should accept a missing runner.
    """

    runner_file = (
        tmp_path
        / "missing.cmd"
    )

    result = remove_runner_file(
        runner_file=runner_file,
    )

    assert result == {
        "success": True,
        "removed": False,
        "status": "ALREADY REMOVED",
        "runner_file": str(
            runner_file.resolve()
        ),
    }


def test_should_reject_runner_directory(
    tmp_path,
):
    """
    Runner path must not resolve to a directory.
    """

    runner_path = (
        tmp_path
        / "runner.cmd"
    )

    runner_path.mkdir()

    with pytest.raises(
        RuntimeError,
        match="runner path is not a file",
    ):

        remove_runner_file(
            runner_file=runner_path,
        )


# ==========================================================
# Complete Workflow
# ==========================================================

def test_should_execute_complete_uninstall(
    tmp_path,
):
    """
    Uninstall workflow should remove tasks and runner while
    preserving Founder data.
    """

    task_results = [
        {
            "success": True,
            "task_name": task_name,
            "status": "REMOVED",
        }
        for task_name in TASK_NAMES
    ]

    runner_result = {
        "success": True,
        "removed": True,
        "status": "REMOVED",
        "runner_file": str(
            (
                tmp_path
                / "runner.cmd"
            ).resolve()
        ),
    }

    received_runner = None

    def fake_remove_tasks():

        return task_results

    def fake_remove_runner(
        *,
        runner_file,
    ):

        nonlocal received_runner

        received_runner = runner_file

        return runner_result

    runner_file = (
        tmp_path
        / "runner.cmd"
    )

    result = execute_scheduler_uninstall(
        remove_tasks=fake_remove_tasks,
        remove_runner=fake_remove_runner,
        runner_file=runner_file,
    )

    assert received_runner == runner_file

    assert result == {
        "success": True,
        "tasks": task_results,
        "runner": runner_result,
        "configuration_preserved": True,
        "snapshots_preserved": True,
        "source_code_preserved": True,
    }


def test_should_return_zero_for_successful_uninstall():
    """
    Successful uninstall should return exit code zero.
    """

    result = run_scheduler_uninstaller(
        execute=lambda: {
            "success": True,
            "tasks": [],
            "runner": {
                "status": "ALREADY REMOVED",
                "runner_file": "runner.cmd",
            },
        },
    )

    assert result == 0


def test_should_return_one_for_failed_uninstall():
    """
    Failed uninstall should return non-zero exit code.
    """

    def failing_execution():

        raise RuntimeError(
            "Access is denied."
        )

    result = run_scheduler_uninstaller(
        execute=failing_execution,
    )

    assert result == 1