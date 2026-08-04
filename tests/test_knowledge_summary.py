"""
Tests for DexSato Knowledge Summary.
"""

from scanner.knowledge_summary import summarize


def build_event(decision, confidence):

    return {
        "decision": decision,
        "confidence": confidence,
    }


# ==================================================
# Empty History
# ==================================================

def test_should_return_empty_summary():

    summary = summarize([])

    assert summary.total_events == 0

    assert summary.latest_decision is None

    assert summary.latest_confidence is None

    assert summary.decision_frequency == {}

    assert summary.most_common_decision is None


# ==================================================
# Single Event
# ==================================================

def test_should_summarize_single_event():

    history = [

        build_event(
            "WATCH",
            "MEDIUM",
        )

    ]

    summary = summarize(history)

    assert summary.total_events == 1

    assert summary.latest_decision == "WATCH"

    assert summary.latest_confidence == "MEDIUM"

    assert summary.decision_frequency == {

        "WATCH": 1,
    }

    assert summary.most_common_decision == "WATCH"


# ==================================================
# Multiple Events
# ==================================================

def test_should_count_decision_frequency():

    history = [

        build_event("WATCH", "MEDIUM"),

        build_event("WATCH", "MEDIUM"),

        build_event("IGNORE", "LOW"),

        build_event("REVIEW", "MEDIUM"),

        build_event("WATCH", "MEDIUM"),

    ]

    summary = summarize(history)

    assert summary.total_events == 5

    assert summary.decision_frequency == {

        "WATCH": 3,

        "IGNORE": 1,

        "REVIEW": 1,
    }

    assert summary.most_common_decision == "WATCH"


# ==================================================
# Latest Event
# ==================================================

def test_should_use_latest_history_item():

    history = [

        build_event("ALERT", "HIGH"),

        build_event("WATCH", "MEDIUM"),

        build_event("IGNORE", "LOW"),

    ]

    summary = summarize(history)

    assert summary.latest_decision == "ALERT"

    assert summary.latest_confidence == "HIGH"