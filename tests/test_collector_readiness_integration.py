import asyncio
import sqlite3
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI

from app.main import application_lifespan, health_readiness, readiness_status


def _write_ready_storage(directory, *, generated_at=None):
    from application import solana_discovery_feed_service as feed_service

    (directory / "state.json").write_text('{"candidates": {}}', encoding="utf-8")
    status = '{"metrics": {}}'
    if generated_at is not None:
        status = f'{{"generated_at": "{generated_at}", "metrics": {{}}}}'
    (directory / "status.json").write_text(status, encoding="utf-8")
    with sqlite3.connect(directory / feed_service.DISCOVERY_ARCHIVE_DB) as connection:
        connection.execute("CREATE TABLE discoveries (token_address TEXT PRIMARY KEY)")
    return feed_service


def test_disabled_collector_keeps_existing_readiness_contract_healthy(tmp_path):
    feed_service = _write_ready_storage(tmp_path)
    with (
        patch.dict("os.environ", {"DEXSATO_COLLECTOR_ENABLED": "false"}),
        patch.object(feed_service, "DEFAULT_OUTPUT_DIR", tmp_path),
    ):
        ready, checks = readiness_status()
        response = health_readiness()

    assert ready is True
    assert checks["collector_storage"] == "ready"
    assert checks["discovery_archive"] == "ready"
    assert checks["collector_fresh"] == "ready"
    assert response.status_code == 200


def test_enabled_collector_makes_stale_status_not_ready(tmp_path):
    feed_service = _write_ready_storage(
        tmp_path, generated_at="2020-01-01T00:00:00+00:00"
    )
    with (
        patch.dict("os.environ", {"DEXSATO_COLLECTOR_ENABLED": "true"}),
        patch.object(feed_service, "DEFAULT_OUTPUT_DIR", tmp_path),
    ):
        ready, checks = readiness_status()
        response = health_readiness()

    assert ready is False
    assert checks["collector_storage"] == "ready"
    assert checks["discovery_archive"] == "ready"
    assert checks["collector_fresh"] == "stale"
    assert response.status_code == 503


def test_application_lifespan_starts_and_stops_scheduler():
    async def scenario():
        scheduler = Mock()
        scheduler.start = AsyncMock()
        scheduler.stop = AsyncMock()
        application = FastAPI()
        with patch(
            "app.main.CollectorScheduler.from_environment", return_value=scheduler
        ):
            async with application_lifespan(application):
                assert application.state.collector_scheduler is scheduler
                scheduler.start.assert_awaited_once()
            scheduler.stop.assert_awaited_once()

    asyncio.run(scenario())
