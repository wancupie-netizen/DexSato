"""
Tests for AlphaRadar V1 FastAPI Application.
"""

from unittest.mock import patch

from fastapi import (
    FastAPI,
    HTTPException,
)

from app.main import (
    APP_TITLE,
    APP_VERSION,
    HOST,
    PORT,
    app,
    build_current_dashboard_data,
    dashboard_api,
    founder_home,
    health_check,
    telegram_send,
)


SNAPSHOT = {
    "generated_at": (
        "2026-07-24T08:00:00+00:00"
    ),
    "total_coins": 1,
    "available_coins": 1,
    "unavailable_coins": 0,
    "coins": [
        {
            "token": "BTC",
            "available": True,
        }
    ],
}


def test_should_create_fastapi_application():
    """
    Application should expose FastAPI.
    """

    assert isinstance(
        app,
        FastAPI,
    )

    assert app.title == APP_TITLE

    assert app.version == APP_VERSION


@patch(
    "app.main.render_founder_snapshot_dashboard"
)
@patch(
    "app.main.load_current_snapshot"
)
def test_should_render_snapshot_dashboard(
    mock_load,
    mock_render,
):
    """
    Root route should read and render the snapshot.
    """

    mock_load.return_value = SNAPSHOT

    mock_render.return_value = (
        "<html>Snapshot Dashboard</html>"
    )

    assert founder_home() == (
        "<html>Snapshot Dashboard</html>"
    )

    mock_render.assert_called_once_with(
        SNAPSHOT,
    )


@patch(
    "app.main.load_current_snapshot"
)
def test_should_build_current_dashboard_data(
    mock_load,
):
    """
    Telegram should receive snapshot coin data.
    """

    mock_load.return_value = SNAPSHOT

    assert build_current_dashboard_data() == (
        SNAPSHOT["coins"]
    )


@patch(
    "app.main.load_current_snapshot"
)
def test_should_return_snapshot_api(
    mock_load,
):
    """
    API should return the complete snapshot.
    """

    mock_load.return_value = SNAPSHOT

    assert dashboard_api() == SNAPSHOT


@patch(
    "app.main.send_telegram_alert"
)
@patch(
    "app.main.build_current_dashboard_data"
)
def test_should_send_snapshot_to_telegram(
    mock_build_data,
    mock_send,
):
    """
    Manual Telegram endpoint should use snapshot data.
    """

    mock_build_data.return_value = (
        SNAPSHOT["coins"]
    )

    mock_send.return_value = {
        "success": True,
        "coins": 1,
    }

    result = telegram_send()

    assert result["success"] is True

    mock_send.assert_called_once_with(
        dashboard_data=SNAPSHOT["coins"],
    )


@patch(
    "app.main.load_current_snapshot"
)
def test_should_reject_missing_snapshot(
    mock_load,
):
    """
    Missing snapshot should return service unavailable.
    """

    mock_load.side_effect = FileNotFoundError(
        "Latest AlphaRadar snapshot is not available."
    )

    try:

        founder_home()

    except HTTPException as error:

        assert error.status_code == 503

        assert (
            "snapshot is not available"
            in error.detail
        )

    else:

        raise AssertionError(
            "HTTPException was not raised."
        )


def test_should_return_healthy_status():
    """
    Health endpoint should remain available.
    """

    assert health_check() == {
        "status": "ok",
        "application": APP_TITLE,
        "version": APP_VERSION,
    }


def test_should_use_local_server_defaults():
    """
    Local launch settings should remain stable.
    """

    assert HOST == "127.0.0.1"

    assert PORT == 8000