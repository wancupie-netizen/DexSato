"""
DexSato Knowledge Summary

Summarize historical Intelligence Events.

Responsibilities
----------------
- Count historical events
- Summarize decision frequency
- Find latest decision
- Find latest confidence
- Find most common decision

This module does NOT:
- access databases
- detect patterns
- enrich intelligence
- make decisions
"""

from collections import Counter

from scanner.models import KnowledgeSummary


def summarize(history: list[dict]) -> KnowledgeSummary:
    """
    Build a Knowledge Summary.
    """

    if not history:

        return KnowledgeSummary(
            total_events=0,
            latest_decision=None,
            latest_confidence=None,
            decision_frequency={},
            most_common_decision=None,
        )

    decision_frequency = Counter(
        item["decision"]
        for item in history
    )

    latest = history[0]

    return KnowledgeSummary(
        total_events=len(history),

        latest_decision=latest["decision"],

        latest_confidence=latest["confidence"],

        decision_frequency=dict(decision_frequency),

        most_common_decision=decision_frequency.most_common(1)[0][0],
    )