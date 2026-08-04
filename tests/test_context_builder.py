"""
Tests for DexSato Context Builder.
"""

from scanner.context_builder import build_context
from scanner.models import KnowledgeContext, KnowledgeSummary


def test_should_build_context_from_history():

    history = [

        {
            "decision": "WATCH",
            "confidence": "MEDIUM",
        },

        {
            "decision": "IGNORE",
            "confidence": "LOW",
        }

    ]

    context = build_context(history)

    assert isinstance(
        context,
        KnowledgeContext,
    )

    assert isinstance(
        context.summary,
        KnowledgeSummary,
    )

    assert context.history == history

    assert context.summary.total_events == 2

    assert context.summary.latest_decision == "WATCH"

    assert context.patterns == []

    assert context.trend is None


def test_should_support_empty_history():

    context = build_context([])

    assert context.summary.total_events == 0

    assert context.history == []

    assert context.patterns == []

    assert context.trend is None


def test_should_include_detected_patterns():

    history = [

        {
            "decision": "WATCH",
            "confidence": "MEDIUM",
        },

        {
            "decision": "WATCH",
            "confidence": "MEDIUM",
        },

        {
            "decision": "WATCH",
            "confidence": "MEDIUM",
        },

    ]

    context = build_context(history)

    assert len(context.patterns) == 1

    assert context.patterns[0].name == "Persistent Watch"