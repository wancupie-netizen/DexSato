from copy import deepcopy

from application.homepage_decision_teaser import build_homepage_decision_teaser
from tests.test_founder_dexsato_dashboard_presenter import SNAPSHOT


def _coin():
    return deepcopy(SNAPSHOT["coins"][0])


def test_teaser_exposes_actual_4h_evidence_and_pending_condition():
    teaser = build_homepage_decision_teaser(_coin())

    assert [item["label"] for item in teaser["evidence"]] == [
        "4H bias", "RSI(14)", "Relative volume",
    ]
    assert teaser["evidence"][0]["value"] == "Bullish Developing"
    assert teaser["evidence"][1]["value"] == "56.80"
    assert teaser["evidence"][2]["value"] == "1.70×"
    assert teaser["next_confirmation"]["label"] == "Volume confirms participation"


def test_material_scan_change_has_highest_summary_priority():
    coin = _coin()
    coin["change_since_previous"] = {
        "status": "CHANGED",
        "headline": "Decision changed from REVIEW to ALERT",
    }
    coin["trader_decision_brief"] = {
        "status": "AVAILABLE", "headline": "Generic brief",
    }

    teaser = build_homepage_decision_teaser(coin)

    assert teaser["context"] == "CHANGED SINCE PREVIOUS SCAN"
    assert teaser["headline"] == "Decision changed from REVIEW to ALERT"


def test_unchanged_scan_is_stated_without_inventing_new_narrative():
    coin = _coin()
    coin["change_since_previous"] = {
        "status": "UNCHANGED",
        "headline": "No material evidence change since the previous scan",
    }

    teaser = build_homepage_decision_teaser(coin)

    assert teaser["context"] == "SINCE PREVIOUS SCAN"
    assert teaser["headline"] == "No material evidence change since the previous scan"


def test_follow_through_is_used_when_no_scan_change_is_available():
    coin = _coin()
    coin["evidence_follow_through"] = {
        "status": "AVAILABLE",
        "evaluations": [{
            "horizon": "4H",
            "result": "SUPPORTIVE",
            "summary": "Price action supported the recorded bias.",
        }],
    }

    teaser = build_homepage_decision_teaser(coin)

    assert teaser["headline"] == "4H evidence follow-through is supportive"
    assert teaser["summary"] == "Price action supported the recorded bias."


def test_missing_technical_data_has_safe_fallback():
    teaser = build_homepage_decision_teaser(deepcopy(SNAPSHOT["coins"][1]))

    assert teaser["evidence"] == []
    assert teaser["next_confirmation"]["label"] == "Await the next material evidence change"
