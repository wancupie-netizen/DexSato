"""
Tests for AlphaRadar Environment Configuration.
"""

import os

import pytest

from application.environment_config import (
    DEFAULT_SCAN_TIMES,
    get_configuration_status,
    get_scan_times,
    load_environment,
    normalize_scan_time,
)


# ==========================================================
# Environment Loading
# ==========================================================

def test_should_load_existing_env_file(
    tmp_path,
    monkeypatch,
):
    """
    Existing .env values should become process environment
    variables.
    """

    env_file = (
        tmp_path
        / ".env"
    )

    env_file.write_text(
        (
            "TELEGRAM_BOT_TOKEN=test-token\n"
            "TELEGRAM_CHAT_ID=123456\n"
            "PUBLIC_DASHBOARD_URL="
            "https://app.alpharadar.ai\n"
            "SCAN_TIME_1=07:30\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv(
        "TELEGRAM_BOT_TOKEN",
        raising=False,
    )

    monkeypatch.delenv(
        "TELEGRAM_CHAT_ID",
        raising=False,
    )

    monkeypatch.delenv(
        "PUBLIC_DASHBOARD_URL",
        raising=False,
    )

    monkeypatch.delenv(
        "SCAN_TIME_1",
        raising=False,
    )

    result = load_environment(
        env_file=env_file,
    )

    assert result["success"] is True

    assert result["env_file_exists"] is True

    assert result["loaded"] is True

    assert os.environ[
        "TELEGRAM_BOT_TOKEN"
    ] == "test-token"

    assert os.environ[
        "TELEGRAM_CHAT_ID"
    ] == "123456"

    assert os.environ[
        "PUBLIC_DASHBOARD_URL"
    ] == "https://app.alpharadar.ai"

    assert os.environ[
        "SCAN_TIME_1"
    ] == "07:30"


def test_should_accept_missing_env_file(
    tmp_path,
):
    """
    Missing .env should return a safe status instead of failing.
    """

    env_file = (
        tmp_path
        / ".env"
    )

    result = load_environment(
        env_file=env_file,
    )

    assert result == {
        "success": True,
        "env_file": str(
            env_file.resolve()
        ),
        "env_file_exists": False,
        "loaded": False,
    }


def test_should_preserve_existing_environment_value(
    tmp_path,
    monkeypatch,
):
    """
    Operating-system environment variables should take
    priority by default.
    """

    env_file = (
        tmp_path
        / ".env"
    )

    env_file.write_text(
        (
            "TELEGRAM_BOT_TOKEN="
            "file-token\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "TELEGRAM_BOT_TOKEN",
        "windows-token",
    )

    load_environment(
        env_file=env_file,
    )

    assert os.environ[
        "TELEGRAM_BOT_TOKEN"
    ] == "windows-token"


def test_should_override_environment_when_requested(
    tmp_path,
    monkeypatch,
):
    """
    Explicit override should allow .env to replace a process
    environment value.
    """

    env_file = (
        tmp_path
        / ".env"
    )

    env_file.write_text(
        (
            "TELEGRAM_BOT_TOKEN="
            "file-token\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "TELEGRAM_BOT_TOKEN",
        "windows-token",
    )

    load_environment(
        env_file=env_file,
        override=True,
    )

    assert os.environ[
        "TELEGRAM_BOT_TOKEN"
    ] == "file-token"


# ==========================================================
# Scan Time Validation
# ==========================================================

@pytest.mark.parametrize(
    (
        "raw_value",
        "expected",
    ),
    [
        (
            "08:00",
            "08:00",
        ),
        (
            " 14:00 ",
            "14:00",
        ),
        (
            "20:00",
            "20:00",
        ),
        (
            "7:05",
            "07:05",
        ),
    ],
)
def test_should_normalize_scan_time(
    raw_value,
    expected,
):
    """
    Valid local times should become consistent HH:MM values.
    """

    assert normalize_scan_time(
        raw_value,
    ) == expected


@pytest.mark.parametrize(
    "invalid_value",
    [
        "",
        "24:00",
        "08",
        "8pm",
        "08:60",
        "not-a-time",
    ],
)
def test_should_reject_invalid_scan_time(
    invalid_value,
):
    """
    Invalid scan times should fail before task installation.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Scan time must use "
            "24-hour HH:MM format"
        ),
    ):

        normalize_scan_time(
            invalid_value,
        )


def test_should_use_default_scan_times():
    """
    Missing configuration should use Founder V1 defaults.
    """

    result = get_scan_times(
        environment={},
    )

    assert result == (
        DEFAULT_SCAN_TIMES
    )


def test_should_read_configured_scan_times():
    """
    Configured values should replace default scan times.
    """

    result = get_scan_times(
        environment={
            "SCAN_TIME_1": "09:00",
            "SCAN_TIME_2": "15:00",
            "SCAN_TIME_3": "21:00",
        },
    )

    assert result == (
        "09:00",
        "15:00",
        "21:00",
    )


def test_should_reject_duplicate_scan_times():
    """
    Windows tasks must not be registered at duplicate times.
    """

    with pytest.raises(
        ValueError,
        match=(
            "scan times must be unique"
        ),
    ):

        get_scan_times(
            environment={
                "SCAN_TIME_1": "08:00",
                "SCAN_TIME_2": "08:00",
                "SCAN_TIME_3": "20:00",
            },
        )


# ==========================================================
# Safe Configuration Status
# ==========================================================

def test_should_report_ready_configuration(
    tmp_path,
):
    """
    Configuration status should confirm readiness without
    exposing credential values.
    """

    env_file = (
        tmp_path
        / ".env"
    )

    env_file.write_text(
        "",
        encoding="utf-8",
    )

    result = get_configuration_status(
        environment={
            "TELEGRAM_BOT_TOKEN": (
                "secret-token"
            ),
            "TELEGRAM_CHAT_ID": "123456",
            "PUBLIC_DASHBOARD_URL": "",
            "SCAN_TIME_1": "08:00",
            "SCAN_TIME_2": "14:00",
            "SCAN_TIME_3": "20:00",
        },
        env_file=env_file,
    )

    assert result["ready"] is True

    assert (
        result[
            "telegram_bot_token_configured"
        ]
        is True
    )

    assert (
        result[
            "telegram_chat_id_configured"
        ]
        is True
    )

    assert (
        result[
            "public_dashboard_url_configured"
        ]
        is False
    )

    assert result["scan_times"] == (
        "08:00",
        "14:00",
        "20:00",
    )

    assert "secret-token" not in str(
        result,
    )


def test_should_report_public_dashboard_configuration(
    tmp_path,
):
    """
    Public dashboard status should be reported without exposing
    its URL.
    """

    result = get_configuration_status(
        environment={
            "TELEGRAM_BOT_TOKEN": "secret-token",
            "TELEGRAM_CHAT_ID": "123456",
            "PUBLIC_DASHBOARD_URL": (
                "https://app.alpharadar.ai"
            ),
        },
        env_file=(
            tmp_path
            / ".env"
        ),
    )

    assert (
        result[
            "public_dashboard_url_configured"
        ]
        is True
    )

    assert (
        "https://app.alpharadar.ai"
        not in str(
            result,
        )
    )