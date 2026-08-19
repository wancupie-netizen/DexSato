from application.market_scan_history import (
    MAX_SCAN_HISTORY, attach_recent_scan_history, build_scan_history_point,
)


def _coin(token="BTC", rsi=48.2):
    return {"token": token, "decision": "REVIEW", "confidence": "MEDIUM",
            "price": 64000, "technical_evidence": {
                "outlook": {"bias": "BEARISH_DEVELOPING"},
                "metrics": {"rsi_14": {"value": rsi},
                            "relative_volume_20": {"value": .78}},
            }}


def test_builds_compact_auditable_history_point():
    point = build_scan_history_point(_coin(), recorded_at="2026-08-19T04:00:00+00:00")
    assert point["technical_bias"] == "BEARISH_DEVELOPING"
    assert point["rsi_14"] == 48.2
    assert point["relative_volume"] == .78


def test_carries_forward_history_and_appends_current_scan():
    previous = {"coins": [{**_coin(), "recent_scan_history": [
        build_scan_history_point(_coin( rsi=50), recorded_at="2026-08-19T00:00:00+00:00")
    ]}]}
    current = {"generated_at": "2026-08-19T04:00:00+00:00", "coins": [_coin()]}
    attach_recent_scan_history(current, previous)
    history = current["coins"][0]["recent_scan_history"]
    assert len(history) == 2
    assert history[-1]["rsi_14"] == 48.2


def test_history_is_bounded_and_deduplicated():
    carried = [
        build_scan_history_point(_coin(), recorded_at=f"2026-08-{day:02d}T00:00:00+00:00")
        for day in range(1, 20)
    ]
    previous = {"coins": [{**_coin(), "recent_scan_history": carried}]}
    current = {"generated_at": "2026-08-19T00:00:00+00:00", "coins": [_coin()]}
    attach_recent_scan_history(current, previous)
    history = current["coins"][0]["recent_scan_history"]
    assert len(history) == MAX_SCAN_HISTORY
    assert len({point["recorded_at"] for point in history}) == MAX_SCAN_HISTORY
