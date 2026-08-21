from copy import deepcopy

from application.decision_readiness_service import (
    attach_decision_readiness,
    build_decision_readiness,
)
from tests.test_founder_dexsato_dashboard_presenter import SNAPSHOT


def _coin():
    coin = deepcopy(SNAPSHOT["coins"][0])
    coin["evidence_health"] = {"status": "FRESH", "technical_usable": True}
    return coin


def test_developing_when_defined_conditions_remain_pending():
    result = build_decision_readiness(_coin())

    assert result["status"] == "DEVELOPING"
    assert result["confirmation"] == {"met": 1, "pending": 1, "total": 2}
    assert result["pending_conditions"] == ["Volume confirms participation"]


def test_well_supported_requires_three_met_directional_conditions():
    coin = _coin()
    coin["technical_evidence"]["outlook"]["confirmation"] = [
        {"label": "Trend", "status": "MET"},
        {"label": "RSI", "status": "MET"},
        {"label": "Volume", "status": "MET"},
        {"label": "Structure", "status": "PENDING"},
    ]

    result = build_decision_readiness(coin)

    assert result["status"] == "WELL_SUPPORTED"
    assert result["confirmation"]["met"] == 3


def test_opposing_directional_evidence_is_conflicted():
    coin = _coin()
    coin["reasons"] = ["DISTRIBUTION", "RISKY_ACTIVITY"]

    result = build_decision_readiness(coin)

    assert result["status"] == "CONFLICTED"
    assert "bearish" in result["conflicts"][0]
    assert "bullish" in result["conflicts"][0]


def test_stale_evidence_takes_priority_over_alignment():
    coin = _coin()
    coin["evidence_health"] = {"status": "STALE", "technical_usable": False}

    result = build_decision_readiness(coin)

    assert result["status"] == "STALE"
    assert "historical context" in result["summary"]


def test_reference_market_is_context_only():
    result = build_decision_readiness(deepcopy(SNAPSHOT["coins"][2]))

    assert result["status"] == "CONTEXT_ONLY"
    assert result["confirmation"]["total"] == 0


def test_attach_adds_readiness_to_snapshot_coins():
    snapshot = {"coins": [_coin()]}

    attach_decision_readiness(snapshot)

    assert snapshot["coins"][0]["decision_readiness"]["status"] == "DEVELOPING"
