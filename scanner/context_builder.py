"""
DexSato Context Builder

Build a Knowledge Context from historical knowledge.

Responsibilities
----------------
- Build KnowledgeContext
- Generate KnowledgeSummary
- Prepare context for enrichment

This module does NOT:
- access databases
- detect patterns
- make decisions
"""

from scanner.models import KnowledgeContext
from scanner.knowledge_summary import summarize
from scanner.pattern_engine import detect_patterns


def build_context(history):
    """
    Build a KnowledgeContext.

    Parameters
    ----------
    history : list[dict]

    Returns
    -------
    KnowledgeContext
    """

    summary = summarize(history)

    patterns = detect_patterns(history)

    return KnowledgeContext(
    history=history,
    summary=summary,
    patterns=patterns,
    trend=None,
    )