import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import main
from application.legacy_discovery_archive import (
    ArchiveUnavailable, render_history_index, render_history_token,
)
from application.product_entitlement_policy import PRO_ENTITLEMENTS, PUBLIC_ENTITLEMENTS


def _archive(path):
    with sqlite3.connect(path / "discovery_archive.sqlite3") as db:
        db.execute(
            "CREATE TABLE discoveries (token_address TEXT PRIMARY KEY, "
            "pair_address TEXT NOT NULL, payload_json TEXT NOT NULL, "
            "first_qualified_at TEXT NOT NULL, last_qualified_at TEXT NOT NULL, "
            "last_seen_at TEXT, currently_qualified INTEGER NOT NULL DEFAULT 0)"
        )
        db.execute(
            "INSERT INTO discoveries VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("token-a", "pair-a", '{"symbol":"<AAA>"}',
             "2026-09-01", "2026-09-02", "2026-09-02", 1),
        )


def _policy(tier):
    return SimpleNamespace(available=True, principal=None), tier


def test_reader_uses_archive_without_state_or_status(tmp_path):
    _archive(tmp_path)
    database = tmp_path / "discovery_archive.sqlite3"
    before = database.read_bytes()
    page = render_history_index(directory=tmp_path)
    token = render_history_token("token-a", directory=tmp_path)
    assert "token-a" in page and "&lt;AAA&gt;" in page
    assert token is not None and "pair-a" in token
    assert "jupiter-order" not in token
    assert database.read_bytes() == before
    assert not (tmp_path / "state.json").exists()
    assert not (tmp_path / "status.json").exists()


def test_missing_archive_fails_without_creating_database(tmp_path):
    with pytest.raises(ArchiveUnavailable):
        render_history_index(directory=tmp_path)
    assert not (tmp_path / "discovery_archive.sqlite3").exists()


def test_disabled_collector_historical_urls_and_api_410(tmp_path):
    _archive(tmp_path)
    with (
        patch.object(main, "collector_enabled", return_value=False),
        patch("application.legacy_discovery_archive.discovery_storage_dir", return_value=tmp_path),
        patch.object(main, "_request_entitlement_policy", return_value=_policy(PRO_ENTITLEMENTS)),
    ):
        client = TestClient(main.app)
        assert client.get("/discovery/solana").status_code == 200
        assert client.get("/discovery/solana/token-a").status_code == 200
        assert client.get("/discovery/solana/missing").status_code == 404
        for url in (
            "/api/discovery/solana/engine",
            "/api/discovery/solana/token-a/candles",
            "/api/discovery/solana/token-a/transactions",
            "/api/discovery/solana/token-a/jupiter-quote",
            "/api/discovery/solana/token-a/wallet-balance",
        ):
            assert client.get(url).status_code == 410, url
        for url in (
            "/api/discovery/solana/token-a/jupiter-order",
            "/api/discovery/solana/token-a/jupiter-execute",
        ):
            assert client.post(url, json={}).status_code == 410, url


def test_disabled_collector_still_requires_pro(tmp_path):
    _archive(tmp_path)
    with (
        patch.object(main, "collector_enabled", return_value=False),
        patch("application.legacy_discovery_archive.discovery_storage_dir", return_value=tmp_path),
        patch.object(main, "_request_entitlement_policy", return_value=_policy(PUBLIC_ENTITLEMENTS)),
    ):
        client = TestClient(main.app)
        assert client.get("/discovery/solana").status_code == 403
        assert client.get("/discovery/solana/token-a").status_code == 403
        assert client.get("/api/discovery/solana/engine").status_code == 403


def test_missing_archive_returns_503_for_historical_urls(tmp_path):
    with (
        patch.object(main, "collector_enabled", return_value=False),
        patch("application.legacy_discovery_archive.discovery_storage_dir", return_value=tmp_path),
        patch.object(main, "_request_entitlement_policy", return_value=_policy(PRO_ENTITLEMENTS)),
    ):
        client = TestClient(main.app)
        assert client.get("/discovery/solana").status_code == 503
        assert client.get("/discovery/solana/token-a").status_code == 503


def test_active_collector_keeps_existing_engine_api():
    feed = {"status": "active", "rows": []}
    with (
        patch.object(main, "collector_enabled", return_value=True),
        patch.object(main, "load_solana_discovery_engine_feed", return_value=feed) as loader,
        patch.object(main, "_request_entitlement_policy", return_value=_policy(PRO_ENTITLEMENTS)),
    ):
        response = TestClient(main.app).get("/api/discovery/solana/engine")
    assert response.status_code == 200
    assert response.json() == feed
    loader.assert_called_once_with(limit=25)


def test_active_collector_keeps_list_and_token_urls():
    market_feeds = {
        "trending": {},
        "top_traded": {},
        "organic_flow": {},
        "recent": {},
    }
    with (
        patch.object(main, "collector_enabled", return_value=True),
        patch.object(main, "_request_entitlement_policy", return_value=_policy(PRO_ENTITLEMENTS)),
        patch.object(
            main, "_load_discovery_page_context",
            return_value=(market_feeds, {}),
        ),
        patch.object(
            main, "apply_market_feed_entitlements",
            return_value=market_feeds,
        ),
        patch.object(main, "load_solana_discovery_feed", return_value={}) as feed,
        patch.object(main, "render_solana_discovery_page", return_value="ACTIVE_LIST"),
        patch.object(main, "load_solana_discovery_token", return_value={}) as token,
        patch.object(main, "render_solana_discovery_token_page", return_value="ACTIVE_TOKEN"),
    ):
        client = TestClient(main.app)
        listing = client.get("/discovery/solana")
        detail = client.get("/discovery/solana/token-a")

    assert listing.status_code == 200 and "ACTIVE_LIST" in listing.text
    assert detail.status_code == 200 and "ACTIVE_TOKEN" in detail.text
    assert feed.call_count == 2
    token.assert_called_once_with("token-a")
