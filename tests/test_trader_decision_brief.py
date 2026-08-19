from application.trader_decision_brief import build_trader_decision_brief


def _technical(bias="BEARISH_DEVELOPING"):
    return {"outlook": {
        "bias": bias,
        "confirmation": [
            {"label": "RSI confirms bearish momentum", "actual": "47.60",
             "requirement": "RSI below 45.00", "status": "PENDING"},
            {"label": "Price holds below EMA50", "actual": "-0.28%",
             "requirement": "Close below EMA50", "status": "MET"},
        ],
        "invalidation": [
            {"label": "4H close recovers above EMA50", "actual": "-0.28%",
             "requirement": "Triggered above 0.00%", "status": "CLEAR"},
        ],
    }}


def test_synthesizes_developing_view_without_creating_trade_instruction():
    brief = build_trader_decision_brief(
        decision="REVIEW", confidence="MEDIUM", technical_evidence=_technical(),
        fundamental_context={"status": "AVAILABLE", "headline": "Official macro signals are mixed"},
        market_catalysts={"catalysts": [{"title": "SEC proposes crypto regulation"}]},
    )
    assert brief["state"] == "DOWNSIDE_EVIDENCE_DEVELOPING"
    assert brief["pending_confirmation"][0]["actual"] == "47.60"
    assert brief["invalidation"][0]["status"] == "CLEAR"
    assert len(brief["context_notes"]) == 2
    assert brief["policy"] == "Evidence synthesis only; not a trade instruction."


def test_mixed_evidence_explicitly_withholds_directional_thesis():
    brief = build_trader_decision_brief(
        decision="ALERT", confidence="HIGH", technical_evidence=_technical("MIXED"),
        fundamental_context={}, market_catalysts={},
    )
    assert brief["state"] == "NO_DIRECTIONAL_THESIS"
    assert "Wait for price structure" in brief["next_action"]


def test_missing_outlook_is_honestly_unavailable():
    brief = build_trader_decision_brief(
        decision="REVIEW", confidence="MEDIUM", technical_evidence={},
        fundamental_context={}, market_catalysts={},
    )
    assert brief["status"] == "INSUFFICIENT_EVIDENCE"
