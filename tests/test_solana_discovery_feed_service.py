import json
import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

from application.solana_discovery_feed_service import load_solana_discovery_feed, load_solana_discovery_record


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def test_loads_phase0_telemetry_without_publishing_candidates(tmp_path):
    (tmp_path / "state.json").write_text(json.dumps({"candidates": {"token-a": {"symbol": "A"}, "token-b": {"symbol": "B"}}}), encoding="utf-8")
    (tmp_path / "status.json").write_text(json.dumps({"collector_status": "running", "generated_at": "2026-08-22T11:55:00+00:00", "metrics": {"pair_resolved": 2, "pair_ready_percent": 99.1}}), encoding="utf-8")

    result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert result["connected"] is True
    assert result["tokens_observed"] == 2
    assert result["pair_resolved"] == 2
    assert result["qualified_candidates"] == 0
    assert result["candidates"] == []
    assert result["updated_label"] == "5 min ago"


def test_fails_closed_when_output_is_missing(tmp_path):
    result = load_solana_discovery_feed(tmp_path, now=NOW)
    assert result["connected"] is False
    assert result["tokens_observed"] is None


def test_default_feed_uses_configured_persistent_storage(tmp_path):
    _write_feed_files(tmp_path, {})
    with patch.dict("os.environ", {"DEXSATO_DISCOVERY_STORAGE_DIR": str(tmp_path)}, clear=True):
        result = load_solana_discovery_feed(now=NOW)
    assert result["connected"] is True
    assert (tmp_path / "discovery_archive.sqlite3").is_file()


def test_fails_closed_for_unexpected_candidate_schema(tmp_path):
    (tmp_path / "state.json").write_text('{"candidates": []}', encoding="utf-8")
    (tmp_path / "status.json").write_text('{"metrics": {}}', encoding="utf-8")
    result = load_solana_discovery_feed(tmp_path, now=NOW)
    assert result["connected"] is False
    assert "schema" in result["message"].lower()


def _write_feed_files(tmp_path, candidates, generated_at="2026-08-22T11:55:00+00:00"):
    (tmp_path / "state.json").write_text(
        json.dumps({"candidates": candidates}),
        encoding="utf-8",
    )
    (tmp_path / "status.json").write_text(
        json.dumps({
            "collector_status": "running",
            "generated_at": generated_at,
            "metrics": {"pair_resolved": len(candidates), "pair_ready_percent": 100},
        }),
        encoding="utf-8",
    )


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_persists_previously_qualified_candidates_across_scans(mock_qualify, tmp_path):
    first = {
        "token_address": "token-a",
        "pair_address": "pair-a",
        "symbol": "AAA",
        "last_seen_at": "2026-08-22T11:54:00+00:00",
    }
    second = {
        "token_address": "token-b",
        "pair_address": "pair-b",
        "symbol": "BBB",
        "last_seen_at": "2026-08-22T11:56:00+00:00",
    }

    _write_feed_files(tmp_path, {"a": first})
    mock_qualify.return_value = [first]
    first_result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert first_result["qualified_candidates"] == 1
    assert [item["token_address"] for item in first_result["candidates"]] == ["token-a"]
    assert first_result["candidates"][0]["currently_qualified"] is True
    assert (tmp_path / "discovery_archive.sqlite3").exists()

    _write_feed_files(tmp_path, {"b": second}, "2026-08-22T11:58:00+00:00")
    mock_qualify.return_value = [second]
    second_result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert second_result["qualified_candidates"] == 1
    assert [item["token_address"] for item in second_result["candidates"]] == ["token-b", "token-a"]
    assert second_result["candidates"][0]["currently_qualified"] is True
    assert second_result["candidates"][1]["currently_qualified"] is False


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_requalified_candidate_updates_without_duplicate_history_row(mock_qualify, tmp_path):
    old = {
        "token_address": "token-a",
        "pair_address": "pair-a",
        "symbol": "AAA",
        "price_usd": 1.0,
        "last_seen_at": "2026-08-22T11:50:00+00:00",
    }
    updated = {**old, "price_usd": 1.5, "change_24h": -8.25, "last_seen_at": "2026-08-22T11:57:00+00:00"}

    _write_feed_files(tmp_path, {"a": old})
    mock_qualify.return_value = [old]
    load_solana_discovery_feed(tmp_path, now=NOW)

    _write_feed_files(tmp_path, {"a": updated}, "2026-08-22T11:59:00+00:00")
    mock_qualify.return_value = [updated]
    result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["token_address"] == "token-a"
    assert result["candidates"][0]["price_usd"] == 1.5
    assert result["candidates"][0]["change_24h"] == -8.25


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_history_survives_scan_with_zero_current_qualifications(mock_qualify, tmp_path):
    candidate = {
        "token_address": "token-a",
        "pair_address": "pair-a",
        "symbol": "AAA",
        "last_seen_at": "2026-08-22T11:54:00+00:00",
    }

    _write_feed_files(tmp_path, {"a": candidate})
    mock_qualify.return_value = [candidate]
    load_solana_discovery_feed(tmp_path, now=NOW)

    mock_qualify.return_value = []
    result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert result["qualified_candidates"] == 0
    assert [item["token_address"] for item in result["candidates"]] == ["token-a"]
    assert result["candidates"][0]["currently_qualified"] is False
    assert result["candidates"][0]["current_qualification"]["code"] == "not_observed_current_scan"


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_persists_actual_current_scan_qualification_diagnostic(mock_qualify, tmp_path):
    candidate = {
        "token_address": "token-a",
        "pair_address": "pair-a",
        "symbol": "AAA",
        "last_seen_at": "2026-08-22T11:54:00+00:00",
    }
    _write_feed_files(tmp_path, {"a": candidate})

    def qualify(_candidates, *, now, diagnostics):
        diagnostics["token-a"] = {
            "evaluated": True,
            "qualified": False,
            "code": "volume_below_threshold",
            "title": "24h activity below qualification threshold",
            "message": "Observed 24h volume $900.00 is below the required $1,000.00.",
        }
        return []

    mock_qualify.side_effect = qualify
    # Seed history first so an unqualified current assessment has an archive row.
    with sqlite3.connect(tmp_path / "discovery_archive.sqlite3") as connection:
        connection.execute("""
            CREATE TABLE discoveries (token_address TEXT PRIMARY KEY, pair_address TEXT NOT NULL,
            payload_json TEXT NOT NULL, first_qualified_at TEXT NOT NULL, last_qualified_at TEXT NOT NULL,
            last_seen_at TEXT, currently_qualified INTEGER NOT NULL DEFAULT 0)
        """)
        connection.execute(
            "INSERT INTO discoveries VALUES (?, ?, ?, ?, ?, ?, 0)",
            ("token-a", "pair-a", json.dumps(candidate), NOW.isoformat(), NOW.isoformat(), candidate["last_seen_at"]),
        )

    result = load_solana_discovery_feed(tmp_path, now=NOW)
    assessment = result["candidates"][0]["current_qualification"]
    assert assessment["code"] == "volume_below_threshold"
    assert assessment["message"] == "Observed 24h volume $900.00 is below the required $1,000.00."
    assert assessment["scan_at"] == "2026-08-22T11:55:00+00:00"


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_archive_is_unbounded_while_front_feed_is_limited_to_100(mock_qualify, tmp_path):
    qualified = [
        {
            "token_address": f"token-{index:03d}",
            "pair_address": f"pair-{index:03d}",
            "symbol": f"T{index:03d}",
            "last_seen_at": "2026-08-22T11:59:00+00:00",
        }
        for index in range(125)
    ]
    _write_feed_files(tmp_path, {"seed": qualified[0]})
    mock_qualify.return_value = qualified

    result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert result["archive_total"] == 125
    assert result["feed_limit"] == 100
    assert len(result["candidates"]) == 100

    with sqlite3.connect(tmp_path / "discovery_archive.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM discoveries").fetchone()[0] == 125
    archived = load_solana_discovery_record("token-124", tmp_path)
    assert archived is not None
    assert archived["token_address"] == "token-124"


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_old_discoveries_remain_archived_when_pushed_off_front_page(mock_qualify, tmp_path):
    original = [
        {
            "token_address": f"old-token-{index:03d}",
            "pair_address": f"old-pair-{index:03d}",
            "symbol": f"OLD{index:03d}",
            "last_seen_at": "2026-08-22T11:50:00+00:00",
        }
        for index in range(100)
    ]
    _write_feed_files(tmp_path, {"seed": original[0]})
    mock_qualify.return_value = original
    first = load_solana_discovery_feed(tmp_path, now=NOW)

    assert first["archive_total"] == 100
    assert len(first["candidates"]) == 100

    newest = {
        "token_address": "new-token",
        "pair_address": "new-pair",
        "symbol": "NEW",
        "last_seen_at": "2026-08-22T11:59:00+00:00",
    }
    _write_feed_files(tmp_path, {"seed": newest}, "2026-08-22T11:59:00+00:00")
    mock_qualify.return_value = [newest]
    second = load_solana_discovery_feed(tmp_path, now=NOW)

    assert second["archive_total"] == 101
    assert len(second["candidates"]) == 100
    assert second["candidates"][0]["token_address"] == "new-token"

    with sqlite3.connect(tmp_path / "discovery_archive.sqlite3") as connection:
        archived = {
            row[0]
            for row in connection.execute("SELECT token_address FROM discoveries").fetchall()
        }

    assert len(archived) == 101
    assert {item["token_address"] for item in original}.issubset(archived)
    assert "new-token" in archived


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_legacy_v36_json_history_is_migrated_without_deletion(mock_qualify, tmp_path):
    legacy = [{
        "token_address": "legacy-token",
        "pair_address": "legacy-pair",
        "symbol": "LEGACY",
        "last_seen_at": "2026-08-21T10:00:00+00:00",
        "last_qualified_at": "2026-08-21T10:00:00+00:00",
        "currently_qualified": False,
    }]
    (tmp_path / "discovery_feed_history.json").write_text(
        json.dumps({"candidates": legacy}),
        encoding="utf-8",
    )
    _write_feed_files(tmp_path, {})
    mock_qualify.return_value = []

    result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert result["archive_total"] == 1
    assert result["candidates"][0]["token_address"] == "legacy-token"
    assert result["candidates"][0]["currently_qualified"] is False
    assert (tmp_path / "discovery_feed_history.json").exists()


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_terminal_searches_archive_before_pagination(mock_qualify, tmp_path):
    qualified = [
        {"token_address": "ber-mint", "pair_address": "ber-pair", "symbol": "BER", "name": "Ber Coin", "dex_id": "pumpswap"},
        {"token_address": "other-mint", "pair_address": "other-pair", "symbol": "OTHER", "name": "Other Coin", "dex_id": "raydium"},
    ]
    _write_feed_files(tmp_path, {"seed": qualified[0]})
    mock_qualify.return_value = qualified
    result = load_solana_discovery_feed(tmp_path, now=NOW, view="archive", query="ber")
    assert result["search_query"] == "ber"
    assert result["view_total"] == 1
    assert [item["token_address"] for item in result["candidates"]] == ["ber-mint"]


@patch("application.solana_discovery_feed_service.qualify_discovery_candidates")
def test_terminal_recent_sort_uses_first_qualified_time(mock_qualify, tmp_path):
    older = {"token_address": "older", "pair_address": "pair-old", "last_seen_at": "2026-08-22T11:59:00+00:00"}
    newer = {"token_address": "newer", "pair_address": "pair-new", "last_seen_at": "2026-08-22T11:50:00+00:00"}
    _write_feed_files(tmp_path, {"seed": older}, "2026-08-22T11:50:00+00:00")
    mock_qualify.return_value = [older]
    load_solana_discovery_feed(tmp_path, now=NOW)
    _write_feed_files(tmp_path, {"seed": newer}, "2026-08-22T11:59:00+00:00")
    mock_qualify.return_value = [newer]
    result = load_solana_discovery_feed(tmp_path, now=NOW, view="recent")
    assert [item["token_address"] for item in result["candidates"]] == ["newer", "older"]
