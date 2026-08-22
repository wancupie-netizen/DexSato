import json
from datetime import datetime, timezone

from application.solana_discovery_feed_service import load_solana_discovery_feed


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


def test_loads_phase0_telemetry_without_publishing_candidates(tmp_path):
    (tmp_path / "state.json").write_text(json.dumps({"candidates": {"token-a": {"symbol": "A"}, "token-b": {"symbol": "B"}}}), encoding="utf-8")
    (tmp_path / "status.json").write_text(json.dumps({"collector_status": "running", "generated_at": "2026-08-22T11:55:00+00:00", "metrics": {"pair_resolved": 2, "pair_ready_percent": 99.1}}), encoding="utf-8")

    result = load_solana_discovery_feed(tmp_path, now=NOW)

    assert result["connected"] is True
    assert result["tokens_observed"] == 2
    assert result["pair_resolved"] == 2
    assert result["qualified_candidates"] is None
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
