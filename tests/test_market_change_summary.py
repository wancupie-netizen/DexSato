from application.market_change_summary import (
    attach_market_change_summaries, build_market_change_summary,
)


def _coin(decision="REVIEW", confidence="MEDIUM", bias="MIXED", rsi=50, volume=1.0):
    return {"token": "BTC", "decision": decision, "confidence": confidence,
            "technical_evidence": {"outlook": {"bias": bias}, "metrics": {
                "rsi_14": {"value": rsi}, "relative_volume_20": {"value": volume},
            }}}


def test_reports_decision_and_auditable_metric_changes():
    summary = build_market_change_summary(
        _coin("ALERT", "HIGH", "BEARISH_DEVELOPING", 47.6, .78),
        _coin("REVIEW", "MEDIUM", "MIXED", 54.39, .32),
    )
    assert summary["status"] == "CHANGED"
    assert summary["headline"] == "Decision changed from REVIEW to ALERT"
    assert [row["label"] for row in summary["changes"]] == [
        "DexSato decision", "Decision confidence", "4H technical bias",
        "RSI(14)", "Relative volume",
    ]
    assert summary["changes"][3]["previous"] == "54.39"
    assert summary["policy"].endswith("no causal inference.")


def test_ignores_small_metric_noise():
    summary = build_market_change_summary(
        _coin(rsi=50.5, volume=1.05), _coin(rsi=50.0, volume=1.0)
    )
    assert summary["status"] == "UNCHANGED"


def test_first_snapshot_is_an_explicit_baseline():
    summary = build_market_change_summary(_coin(), None)
    assert summary["status"] == "BASELINE"


def test_attaches_comparison_by_token():
    current = {"coins": [_coin(rsi=45)]}
    previous = {"coins": [_coin(rsi=55)]}
    attach_market_change_summaries(current, previous)
    assert current["coins"][0]["change_since_previous"]["status"] == "CHANGED"
