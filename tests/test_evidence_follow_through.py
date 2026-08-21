from application.evidence_follow_through import build_evidence_follow_through


def _point(at, bias, price):
    return {"recorded_at": at, "technical_bias": bias, "price": price}


def test_bearish_bias_is_supportive_when_price_falls_after_four_hours():
    result = build_evidence_follow_through([
        _point("2026-08-19T00:00:00+00:00", "BEARISH_DEVELOPING", 100),
        _point("2026-08-19T04:00:00+00:00", "BEARISH_DEVELOPING", 98),
    ])
    evaluation = result["evaluations"][0]
    assert evaluation["horizon"] == "4H"
    assert evaluation["assessment"] == "SUPPORTIVE"
    assert evaluation["price_change_pct"] == -2.0


def test_bearish_bias_is_contradicted_when_price_rises():
    result = build_evidence_follow_through([
        _point("2026-08-19T00:00:00+00:00", "BEARISH_DEVELOPING", 100),
        _point("2026-08-19T04:00:00+00:00", "MIXED", 102),
    ])
    assert result["evaluations"][0]["assessment"] == "CONTRADICTED"


def test_small_move_is_inconclusive_not_a_win_or_loss():
    result = build_evidence_follow_through([
        _point("2026-08-19T00:00:00+00:00", "BULLISH_DEVELOPING", 100),
        _point("2026-08-19T04:00:00+00:00", "BULLISH_DEVELOPING", 100.2),
    ])
    assert result["evaluations"][0]["assessment"] == "INCONCLUSIVE"
    assert "not win rate" in result["policy"]


def test_reports_collecting_until_directional_history_is_old_enough():
    result = build_evidence_follow_through([
        _point("2026-08-19T00:00:00+00:00", "MIXED", 100),
        _point("2026-08-19T04:00:00+00:00", "MIXED", 99),
    ])
    assert result["status"] == "COLLECTING"
    assert result["message"] == "Collecting sufficient scan history."


def test_can_evaluate_four_and_twenty_four_hour_horizons():
    result = build_evidence_follow_through([
        _point("2026-08-18T00:00:00+00:00", "BULLISH_DEVELOPING", 100),
        _point("2026-08-18T20:00:00+00:00", "BULLISH_DEVELOPING", 102),
        _point("2026-08-19T00:00:00+00:00", "BULLISH_DEVELOPING", 104),
    ])
    assert [row["horizon"] for row in result["evaluations"]] == ["4H", "24H"]
