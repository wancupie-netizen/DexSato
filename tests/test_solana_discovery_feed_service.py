import json
from datetime import datetime, timezone
from unittest.mock import patch

from application.solana_discovery_feed_service import load_solana_discovery_feed


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
    assert (tmp_path / "discovery_feed_history.json").exists()

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
    updated = {**old, "price_usd": 1.5, "last_seen_at": "2026-08-22T11:57:00+00:00"}

    _write_feed_files(tmp_path, {"a": old})
    mock_qualify.return_value = [old]
    load_solana_discovery_feed(tmp_path, now=NOW)

    _write_feed_files(tmp_path, {"a": updated}, "2026-08-22T11:59:00+00:00")
    mock_qualify.return_value = [updated]
    result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["token_address"] == "token-a"
    assert result["candidates"][0]["price_usd"] == 1.5


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
