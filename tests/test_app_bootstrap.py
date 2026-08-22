"""
Tests for DexSato V1 FastAPI Application.
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
    admin_system,
    build_current_dashboard_data,
    dashboard_api,
    founder_home,
    health_check,
    market_detail,
    solana_discovery,
    solana_discovery_token,
    system_status_api,
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
    "app.main.collect_system_dashboard_status"
)
@patch(
    "app.main.load_current_snapshot"
)
def test_should_render_snapshot_dashboard(
    mock_load,
    mock_system_status,
    mock_render,
):
    """
    Root route should read and render the snapshot.
    """

    mock_load.return_value = SNAPSHOT

    mock_render.return_value = (
        "<html>Snapshot Dashboard</html>"
    )
    mock_system_status.return_value = {
        "overall_health": "HEALTHY",
    }

    assert founder_home() == (
        "<html>Snapshot Dashboard</html>"
    )

    mock_render.assert_called_once_with(
        SNAPSHOT,
        system_status={
            "overall_health": "HEALTHY",
        },
    )


@patch("app.main.render_solana_discovery_page")
@patch("app.main.load_solana_discovery_feed")
def test_should_render_read_only_solana_discovery(mock_feed, mock_render):
    mock_feed.return_value = {"connected": True}
    mock_render.return_value = "<html>Solana Discovery</html>"

    assert solana_discovery() == "<html>Solana Discovery</html>"
    mock_render.assert_called_once_with({"connected": True})


@patch("app.main.render_solana_discovery_token_page")
@patch("app.main.load_solana_discovery_token")
def test_should_render_qualified_solana_discovery_token(mock_load, mock_render):
    mock_load.return_value = {"token_address": "Token123"}
    mock_render.return_value = "<html>Token workspace</html>"

    assert solana_discovery_token("Token123") == "<html>Token workspace</html>"
    mock_load.assert_called_once_with("Token123")


@patch("app.main.load_solana_discovery_token", return_value=None)
def test_should_not_expose_unknown_solana_discovery_token(mock_load):
    try:
        solana_discovery_token("Unknown")
    except HTTPException as error:
        assert error.status_code == 404
    else:
        raise AssertionError("Expected unknown discovery token to return 404")


@patch("app.main.render_admin_system_page")
@patch("app.main.collect_system_dashboard_status")
@patch("app.main.load_current_snapshot")
def test_should_render_admin_system_console(mock_load, mock_status, mock_render):
    mock_load.return_value = SNAPSHOT
    mock_status.return_value = {"overall_health": "HEALTHY"}
    mock_render.return_value = "<html>Admin Operations</html>"

    assert admin_system() == "<html>Admin Operations</html>"
    mock_render.assert_called_once_with(
        SNAPSHOT,
        system_status={"overall_health": "HEALTHY"},
    )


@patch(
    "app.main.collect_system_dashboard_status"
)
def test_should_return_system_status_api(
    mock_collect,
):
    """
    System endpoint should return operational health data.
    """

    expected = {
        "overall_health": "HEALTHY",
        "latest_run": {
            "telegram_status": "SENT",
        },
    }
    mock_collect.return_value = expected

    assert system_status_api() == expected


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


@patch("app.main.render_market_detail_page")
@patch("app.main.load_current_snapshot")
def test_should_render_market_detail_page(mock_load, mock_render):
    mock_load.return_value = SNAPSHOT
    mock_render.return_value = "<html>BTC workspace</html>"

    assert market_detail("btc") == "<html>BTC workspace</html>"
    mock_render.assert_called_once_with(
        SNAPSHOT["coins"][0],
        generated_at=SNAPSHOT["generated_at"],
    )


@patch("app.main.load_current_snapshot")
def test_should_return_not_found_for_unknown_market(mock_load):
    mock_load.return_value = SNAPSHOT

    try:
        market_detail("UNKNOWN")
    except HTTPException as error:
        assert error.status_code == 404
    else:
        raise AssertionError("Unknown market should return 404.")


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
        "Latest DexSato snapshot is not available."
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
