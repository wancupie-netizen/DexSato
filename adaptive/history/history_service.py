"""
DexSato History Service

Application service for Historical Intelligence.

Responsibilities
----------------
- Load historical experiences
- Build HistorySummary

This module does NOT:
- access databases directly
- perform calculations
- perform AI analysis
"""

from adaptive.history.history_builder import (
    build_history_summary,
)

from adaptive.history.history_repository import (
    find,
)

from adaptive.history.history_summary import (
    HistorySummary,
)


# --------------------------------------------------
# History Service
# --------------------------------------------------

def build_history(
    fingerprint: str,
) -> HistorySummary:
    """
    Build HistorySummary for a fingerprint.
    """

    experiences = find(
        fingerprint,
    )

    return build_history_summary(
        experiences,
    )