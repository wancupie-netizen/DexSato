from copy import deepcopy
from datetime import datetime, timezone

import pytest

from application.evidence_health_service import (
    attach_evidence_health,
    build_evidence_health,
)


NOW = datetime(2026, 8, 21, 14, 0, tzinfo=timezone.utc)


def _coin():
    return {
        "token": "BTC", "asset_class": "crypto", "available": True,
        "scanned_at": "2026-08-21T13:50:00+00:00",
        "trading_venues_status": "AVAILABLE",
        "technical_evidence_status": "AVAILABLE",
        "technical_evidence": {
            "status": "AVAILABLE",
            "candle_closed_at": "2026-08-21T12:00:00+00:00",
        },
        "fundamental_context": {
            "status": "AVAILABLE", "collected_at": "2026-08-01T00:00:00+00:00",
        },
        "market_catalysts": {
            "status": "AVAILABLE", "collected_at": "2026-08-21T13:00:00+00:00",
        },
    }


def test_fresh_required_sources_produce_fresh_health():
    result = build_evidence_health(_coin(), evaluated_at=NOW)

    assert result["status"] == "FRESH"
    assert result["technical_usable"] is True
    assert result["checks"]["technical_4h"]["state"] == "FRESH"


def test_stale_technical_evidence_degrades_safely():
    coin = _coin()
    coin["technical_evidence"]["candle_closed_at"] = "2026-08-20T20:00:00+00:00"

    result = build_evidence_health(coin, evaluated_at=NOW)

    assert result["status"] == "STALE"
    assert result["technical_usable"] is False
    assert "historical context" in result["summary"]


def test_missing_optional_source_is_partial_not_stale():
    coin = _coin()
    coin["market_catalysts"] = {"status": "UNAVAILABLE"}

    result = build_evidence_health(coin, evaluated_at=NOW)

    assert result["status"] == "PARTIAL"
    assert result["technical_usable"] is True


def test_attach_adds_health_to_each_coin():
    snapshot = {"generated_at": NOW.isoformat(), "coins": [_coin()]}

    attach_evidence_health(snapshot)

    assert snapshot["coins"][0]["evidence_health"]["status"] == "FRESH"


def test_naive_evaluation_time_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        build_evidence_health(_coin(), evaluated_at=datetime(2026, 8, 21, 14, 0))
