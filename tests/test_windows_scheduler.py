"""
Tests for AlphaRadar Windows Scheduler.
"""

import subprocess

import pytest

from application.windows_scheduler import (
    TASK_NAMES,
    build_create_task_command,
    build_runner_content,
    build_task_definitions,
    ensure_windows,
    install_windows_tasks,
    write_runner_file,
)


# ==========================================================
# Platform Validation
# ==========================================================

def test_should_accept_windows_platform():
    """
    Windows installations should be accepted.
    """

    ensure_windows(
        platform_name="nt",
    )


def test_should_reject_non_windows_platform():
    """
    Non-Windows systems should fail clearly.
    """

    with pytest.raises(
        RuntimeError,
        match="can only be managed on Windows",
    ):

        ensure_windows(
            platform_name="posix",
        )


# ==========================================================
# Runner Generation
# ==========================================================

def test_should_build_machine_local_runner(
    tmp_path,
):
    """
    Runner should use absolute project, Python, and script
    paths.
    """

    project_root = (
        tmp_path
        / "Alpha Radar"
    )

    python_file = (
        tmp_path
        / "Python"
        / "python.exe"
    )

    scheduler_file = (
        project_root
        / "founder_scheduler.py"
    )

    content = build_runner_content(
        project_root=project_root,
        python_executable=python_file,
        scheduler_file=scheduler_file,
    )

    assert "@echo off" in content

    assert (
        f'cd /d "{project_root.resolve()}"'
        in content
    )

    assert (
        f'"{python_file.resolve()}"'
        in content
    )

    assert (
        f'"{scheduler_file.resolve()}"'
        in content
    )

    assert (
        "exit /b %ALPHARADAR_EXIT_CODE%"
        in content
    )


def test_should_write_runner_file(
    tmp_path,
):
    """
    Runner should be created under the requested location.
    """

    project_root = (
        tmp_path
        / "AlphaRadar"
    )

    project_root.mkdir()

    scheduler_file = (
        project_root
        / "founder_scheduler.py"
    )

    scheduler_file.write_text(
        "print('test')\n",
        encoding="utf-8",
    )

    python_file = (
        tmp_path
        / "python.exe"
    )

    runner_file = (
        tmp_path
        / "output"
        / "automation"
        / "run.cmd"
    )

    result = write_runner_file(
        runner_file=runner_file,
        project_root=project_root,
        python_executable=python_file,
        scheduler_file=scheduler_file,
    )

    assert result == runner_file.resolve()

    assert runner_file.is_file()

    content = runner_file.read_text(
        encoding="utf-8",
    )

    assert (
        str(
            scheduler_file.resolve()
        )
        in content
    )


def test_should_reject_missing_scheduler_file(
    tmp_path,
):
    """
    Installer must not register a runner for a missing script.
    """

    with pytest.raises(
        FileNotFoundError,
        match="founder_scheduler.py was not found",
    ):

        write_runner_file(
            runner_file=(
                tmp_path
                / "run.cmd"
            ),
            scheduler_file=(
                tmp_path
                / "missing.py"
            ),
        )


# ==========================================================
# Task Definitions
# ==========================================================

def test_should_build_three_task_definitions():
    """
    Scan times should map to stable task names.
    """

    result = build_task_definitions(
        scan_times=(
            "08:00",
            "14:00",
            "20:00",
        ),
    )

    assert result == [
        {
            "task_name": TASK_NAMES[0],
            "scan_time": "08:00",
        },
        {
            "task_name": TASK_NAMES[1],
            "scan_time": "14:00",
        },
        {
            "task_name": TASK_NAMES[2],
            "scan_time": "20:00",
        },
    ]


def test_should_reject_wrong_number_of_scan_times():
    """
    Founder V1 requires exactly three daily tasks.
    """

    with pytest.raises(
        ValueError,
        match="exactly three scan times",
    ):

        build_task_definitions(
            scan_times=(
                "08:00",
                "20:00",
            ),
        )


def test_should_build_schtasks_create_command(
    tmp_path,
):
    """
    Command should create one replaceable daily task.
    """

    runner_file = (
        tmp_path
        / "Alpha Radar"
        / "run.cmd"
    )

    result = build_create_task_command(
        task_name="AlphaRadar Founder Scan 1",
        scan_time="08:00",
        runner_file=runner_file,
    )

    assert result == [
        "schtasks.exe",
        "/Create",
        "/TN",
        "AlphaRadar Founder Scan 1",
        "/TR",
        f'"{runner_file.resolve()}"',
        "/SC",
        "DAILY",
        "/ST",
        "08:00",
        "/F",
    ]


# ==========================================================
# Task Installation
# ==========================================================

def test_should_install_all_windows_tasks(
    tmp_path,
):
    """
    Three successful schtasks commands should produce three
    installation results.
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
            stdout="SUCCESS",
            stderr="",
        )

    result = install_windows_tasks(
        scan_times=(
            "08:00",
            "14:00",
            "20:00",
        ),
        runner_file=(
            tmp_path
            / "run.cmd"
        ),
        run_command=fake_run,
        platform_name="nt",
    )

    assert len(
        commands,
    ) == 3

    assert len(
        result,
    ) == 3

    assert result[0][
        "task_name"
    ] == TASK_NAMES[0]

    assert result[0][
        "scan_time"
    ] == "08:00"

    assert result[1][
        "task_name"
    ] == TASK_NAMES[1]

    assert result[1][
        "scan_time"
    ] == "14:00"

    assert result[2][
        "task_name"
    ] == TASK_NAMES[2]

    assert result[2][
        "scan_time"
    ] == "20:00"

    assert all(
        item["success"] is True
        for item in result
    )

    assert all(
        item["returncode"] == 0
        for item in result
    )


def test_should_build_three_schtasks_commands(
    tmp_path,
):
    """
    Installation should generate one create command for each
    configured daily scan.
    """

    commands: list[
        list[str]
    ] = []

    runner_file = (
        tmp_path
        / "run.cmd"
    )

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
            stdout="SUCCESS",
            stderr="",
        )

    install_windows_tasks(
        scan_times=(
            "08:00",
            "14:00",
            "20:00",
        ),
        runner_file=runner_file,
        run_command=fake_run,
        platform_name="nt",
    )

    assert commands == [
        [
            "schtasks.exe",
            "/Create",
            "/TN",
            TASK_NAMES[0],
            "/TR",
            f'"{runner_file.resolve()}"',
            "/SC",
            "DAILY",
            "/ST",
            "08:00",
            "/F",
        ],
        [
            "schtasks.exe",
            "/Create",
            "/TN",
            TASK_NAMES[1],
            "/TR",
            f'"{runner_file.resolve()}"',
            "/SC",
            "DAILY",
            "/ST",
            "14:00",
            "/F",
        ],
        [
            "schtasks.exe",
            "/Create",
            "/TN",
            TASK_NAMES[2],
            "/TR",
            f'"{runner_file.resolve()}"',
            "/SC",
            "DAILY",
            "/ST",
            "20:00",
            "/F",
        ],
    ]


def test_should_fail_when_task_registration_fails(
    tmp_path,
):
    """
    Any failed task registration should stop installation.
    """

    def failing_run(
        command,
    ):

        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="Access is denied.",
        )

    with pytest.raises(
        RuntimeError,
        match="Access is denied",
    ):

        install_windows_tasks(
            scan_times=(
                "08:00",
                "14:00",
                "20:00",
            ),
            runner_file=(
                tmp_path
                / "run.cmd"
            ),
            run_command=failing_run,
            platform_name="nt",
        )


def test_should_include_task_name_in_registration_error(
    tmp_path,
):
    """
    Failed installation should identify the task that could not
    be registered.
    """

    def failing_run(
        command,
    ):

        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="Access is denied.",
        )

    with pytest.raises(
        RuntimeError,
        match=(
            "AlphaRadar Founder Scan 1"
        ),
    ):

        install_windows_tasks(
            scan_times=(
                "08:00",
                "14:00",
                "20:00",
            ),
            runner_file=(
                tmp_path
                / "run.cmd"
            ),
            run_command=failing_run,
            platform_name="nt",
        )


def test_should_reject_task_installation_on_non_windows(
    tmp_path,
):
    """
    Scheduled tasks must not be installed outside Windows.
    """

    with pytest.raises(
        RuntimeError,
        match="can only be managed on Windows",
    ):

        install_windows_tasks(
            scan_times=(
                "08:00",
                "14:00",
                "20:00",
            ),
            runner_file=(
                tmp_path
                / "run.cmd"
            ),
            platform_name="posix",
        )