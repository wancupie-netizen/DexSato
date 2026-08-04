"""
DexSato Knowledge Engine

Public entry point for the Knowledge Engine.

Responsibilities
----------------
- Load historical knowledge
- Build Knowledge Context
- Hide internal implementation

This module does NOT:
- access Supabase directly
- summarize knowledge
- detect patterns
- enrich intelligence
"""

from scanner.knowledge_history import get_history
from scanner.context_builder import build_context
from scanner.models import KnowledgeContext


DEFAULT_HISTORY_LIMIT = 50


def build_knowledge_context(
    token: str,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> KnowledgeContext:
    """
    Build a KnowledgeContext for a token.

    Parameters
    ----------
    token : str

    limit : int

    Returns
    -------
    KnowledgeContext
    """

    history = get_history(
        token=token,
        limit=limit,
    )

    return build_context(history)
    