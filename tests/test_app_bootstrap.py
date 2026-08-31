"""
Tests for DexSato V1 FastAPI Application.
"""

import asyncio
import sqlite3
import threading
import requests
from unittest.mock import AsyncMock, Mock, patch

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
    health_liveness,
    health_readiness,
    market_detail,
    solana_discovery,
    solana_discovery_jupiter_execute,
    solana_discovery_jupiter_order,
    solana_discovery_jupiter_quote,
    solana_discovery_token,
    system_status_api,
    telegram_send,
    readiness_status,
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
    mock_feed.assert_called_once_with(view="qualified", page=1, page_size=25, query="")
    mock_render.assert_called_once_with({"connected": True})


@patch("app.main.render_solana_discovery_token_page")
@patch("app.main.load_solana_discovery_feed")
@patch("app.main.load_solana_discovery_token")
def test_should_render_qualified_solana_discovery_token(mock_load, mock_feed, mock_render):
    mock_load.return_value = {"token_address": "Token123"}
    mock_feed.return_value = {"connected": True, "candidates": []}
    mock_render.return_value = "<html>Token workspace</html>"

    assert solana_discovery_token("Token123") == "<html>Token workspace</html>"
    mock_load.assert_called_once_with("Token123")
    mock_feed.assert_called_once_with()
    mock_render.assert_called_once_with(
        {"token_address": "Token123"},
        feed={"connected": True, "candidates": []},
    )


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


@patch("application.jupiter_quote_service.fetch_jupiter_quote")
def test_should_return_quote_only_jupiter_sandbox(mock_quote):
    mock_quote.return_value = {"status": "QUOTE_READY", "quote_only": True}

    result = solana_discovery_jupiter_quote("11111111111111111111111111111111", "0.1")

    assert result["quote_only"] is True
    mock_quote.assert_called_once_with("11111111111111111111111111111111", "0.1")


@patch("application.jupiter_swap_service.prepare_jupiter_swap")
def test_should_prepare_unsigned_swap_only_after_explicit_risk_acknowledgement(mock_prepare):
    mock_prepare.return_value = {"status": "WALLET_APPROVAL_REQUIRED", "request_id": "order-1"}
    request = Mock()
    request.json = AsyncMock(return_value={
        "amount_sol": "0.1",
        "wallet_address": "11111111111111111111111111111111",
        "risk_acknowledged": True,
    })

    result = asyncio.run(solana_discovery_jupiter_order("22222222222222222222222222222222", request))

    assert result["status"] == "WALLET_APPROVAL_REQUIRED"
    mock_prepare.assert_called_once_with(
        "22222222222222222222222222222222", "0.1", "11111111111111111111111111111111",
        risk_acknowledged=True,
    )


@patch("application.jupiter_swap_service.prepare_jupiter_swap")
def test_jupiter_order_work_runs_outside_the_event_loop_thread(mock_prepare):
    caller_thread = threading.get_ident()

    def prepared(*_args, **_kwargs):
        assert threading.get_ident() != caller_thread
        return {"status": "WALLET_APPROVAL_REQUIRED", "request_id": "thread-order"}

    mock_prepare.side_effect = prepared
    request = Mock()
    request.json = AsyncMock(return_value={
        "amount_sol": "0.1",
        "wallet_address": "11111111111111111111111111111111",
        "risk_acknowledged": True,
    })

    result = asyncio.run(
        solana_discovery_jupiter_order("22222222222222222222222222222222", request)
    )
    assert result["request_id"] == "thread-order"


@patch("application.jupiter_swap_service.prepare_jupiter_swap")
def test_should_preserve_actionable_jupiter_order_error_message(mock_prepare):
    from application.jupiter_quote_service import JupiterQuoteUnavailable

    mock_prepare.side_effect = JupiterQuoteUnavailable(
        "Insufficient SOL balance. Reduce the swap amount or add SOL to your connected wallet."
    )
    request = Mock()
    request.json = AsyncMock(return_value={
        "amount_sol": "0.1",
        "wallet_address": "11111111111111111111111111111111",
        "risk_acknowledged": True,
    })

    try:
        asyncio.run(
            solana_discovery_jupiter_order(
                "22222222222222222222222222222222",
                request,
            )
        )
    except HTTPException as error:
        assert error.status_code == 503
        assert error.detail == (
            "Insufficient SOL balance. Reduce the swap amount or add SOL to your connected wallet."
        )
    else:
        raise AssertionError("Actionable Jupiter order error should be returned as HTTP 503.")

@patch("application.jupiter_swap_service.execute_jupiter_swap")
def test_should_relay_a_wallet_signed_transaction_without_accepting_wallet_secrets(mock_execute):
    mock_execute.return_value = {"status": "SWAP_CONFIRMED", "signature": "555555"}
    request = Mock()
    request.json = AsyncMock(return_value={
        "request_id": "order-1",
        "wallet_address": "11111111111111111111111111111111",
        "signed_transaction": "c2lnbmVk",
    })

    result = asyncio.run(solana_discovery_jupiter_execute("22222222222222222222222222222222", request))

    assert result["status"] == "SWAP_CONFIRMED"
    mock_execute.assert_called_once_with(
        "22222222222222222222222222222222", "order-1",
        "11111111111111111111111111111111", "c2lnbmVk",
    )


@patch("application.jupiter_swap_service.execute_jupiter_swap")
def test_jupiter_execute_work_runs_outside_the_event_loop_thread(mock_execute):
    caller_thread = threading.get_ident()

    def executed(*_args, **_kwargs):
        assert threading.get_ident() != caller_thread
        return {"status": "SWAP_CONFIRMED", "signature": "555555"}

    mock_execute.side_effect = executed
    request = Mock()
    request.json = AsyncMock(return_value={
        "request_id": "order-1",
        "wallet_address": "11111111111111111111111111111111",
        "signed_transaction": "c2lnbmVk",
    })

    result = asyncio.run(
        solana_discovery_jupiter_execute("22222222222222222222222222222222", request)
    )
    assert result["status"] == "SWAP_CONFIRMED"


@patch("application.jupiter_swap_service.prepare_jupiter_swap")
def test_should_reject_unsupported_sensitive_swap_request_fields(mock_prepare):
    request = Mock()
    request.json = AsyncMock(return_value={
        "amount_sol": "0.1",
        "wallet_address": "11111111111111111111111111111111",
        "risk_acknowledged": True,
        "private_key": "must-never-be-accepted",
    })

    try:
        asyncio.run(solana_discovery_jupiter_order("22222222222222222222222222222222", request))
    except HTTPException as error:
        assert error.status_code == 400
        assert "Unsupported" in error.detail
    else:
        raise AssertionError("Expected private-key field to be rejected")
    mock_prepare.assert_not_called()


@patch("application.jupiter_swap_service.prepare_jupiter_swap")
@patch("application.jupiter_swap_service.execute_jupiter_swap")
def test_client_fee_overrides_are_rejected_before_services(mock_execute, mock_prepare):
    for field in ("referralAccount", "referralFee", "feeBps", "feeAccount",
                  "platformFeeBps", "dexsato_integrator_fee_bps", "fee_enabled"):
        for endpoint, body in (
            (solana_discovery_jupiter_order, {
                "amount_sol": "0.1", "wallet_address": "11111111111111111111111111111111",
                "risk_acknowledged": True,
            }),
            (solana_discovery_jupiter_execute, {
                "request_id": "order-1", "wallet_address": "11111111111111111111111111111111",
                "signed_transaction": "c2lnbmVk",
            }),
        ):
            request = Mock()
            request.json = AsyncMock(return_value={**body, field: "client-value"})
            try:
                asyncio.run(endpoint("22222222222222222222222222222222", request))
            except HTTPException as error:
                assert error.status_code == 400
                assert "Unsupported" in error.detail
            else:
                raise AssertionError("Client fee override must be rejected")
    mock_prepare.assert_not_called()
    mock_execute.assert_not_called()


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

        assert error.detail == "Market snapshot is temporarily unavailable."

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

    assert health_liveness() == health_check()


def test_readiness_reports_required_local_components(tmp_path):
    from application import solana_discovery_feed_service as feed_service

    (tmp_path / "state.json").write_text('{"candidates": {}}', encoding="utf-8")
    (tmp_path / "status.json").write_text('{"metrics": {}}', encoding="utf-8")
    with sqlite3.connect(tmp_path / feed_service.DISCOVERY_ARCHIVE_DB) as connection:
        connection.execute("CREATE TABLE discoveries (token_address TEXT PRIMARY KEY)")

    with patch.object(feed_service, "DEFAULT_OUTPUT_DIR", tmp_path):
        ready, checks = readiness_status()
        response = health_readiness()

    assert ready is True
    assert checks == {
        "static": "ready",
        "collector": "ready",
        "archive": "ready",
        "configuration": "ready",
    }
    assert response.status_code == 200


def test_readiness_returns_503_when_discovery_storage_is_missing(tmp_path):
    from application import solana_discovery_feed_service as feed_service

    with patch.object(feed_service, "DEFAULT_OUTPUT_DIR", tmp_path):
        ready, checks = readiness_status()
        response = health_readiness()

    assert ready is False
    assert checks["collector"] == "unavailable"
    assert checks["archive"] == "unavailable"
    assert checks["configuration"] == "ready"
    assert response.status_code == 503


def test_readiness_rejects_corrupt_collector_and_archive_files(tmp_path):
    from application import solana_discovery_feed_service as feed_service

    (tmp_path / "state.json").write_text("not-json", encoding="utf-8")
    (tmp_path / "status.json").write_text('{"metrics": {}}', encoding="utf-8")
    (tmp_path / feed_service.DISCOVERY_ARCHIVE_DB).write_bytes(b"not-sqlite")

    with patch.object(feed_service, "DEFAULT_OUTPUT_DIR", tmp_path):
        ready, checks = readiness_status()

    assert ready is False
    assert checks["collector"] == "unavailable"
    assert checks["archive"] == "unavailable"


def test_should_use_local_server_defaults():
    """
    Local launch settings should remain stable.
    """

    assert HOST == "127.0.0.1"

    assert PORT == 8000



# TRANSACTIONS_FEED_V11_API_ROUTE
def test_transactions_api_returns_exact_pool_service_payload():
    from app.main import solana_discovery_transactions
    expected = {
        "token_address": "Token123", "pair_address": "Pool123",
        "transactions": [{"id": "trade-1", "side": "BUY"}],
        "as_of": "2026-08-26T00:00:01+00:00",
        "source": "GeckoTerminal exact-pool trades",
    }
    with patch("app.main.load_solana_discovery_transactions", return_value=expected) as mock_load:
        assert solana_discovery_transactions("Token123") == expected
    mock_load.assert_called_once_with("Token123")


def test_transactions_api_returns_404_for_unqualified_token():
    from app.main import solana_discovery_transactions
    with patch("app.main.load_solana_discovery_transactions", return_value=None):
        try:
            solana_discovery_transactions("Unknown")
        except HTTPException as error:
            assert error.status_code == 404
            assert error.detail == "Qualified discovery token is not available."
        else:
            raise AssertionError("Expected unknown discovery token to return 404")


def test_transactions_api_returns_503_when_provider_is_unavailable():
    from app.main import solana_discovery_transactions
    with patch("app.main.load_solana_discovery_transactions", side_effect=requests.RequestException("provider unavailable")):
        try:
            solana_discovery_transactions("Token123")
        except HTTPException as error:
            assert error.status_code == 503
            assert error.detail == "Live transaction data is temporarily unavailable."
        else:
            raise AssertionError("Expected provider failure to return 503")


def test_transactions_api_route_is_registered_as_get():
    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if hasattr(route, "path") and hasattr(route, "methods")
    }

    assert (
        "/api/discovery/solana/{token_address}/transactions",
        ("GET",),
    ) in routes
