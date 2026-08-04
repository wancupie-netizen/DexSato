"""
DexSato History Summary

Historical Intelligence Artifact.

Responsibilities
----------------
- Represent historical outcome summary
- Provide immutable historical contract

This module does NOT:
- access databases
- access repositories
- perform predictions
- perform AI analysis
"""

from dataclasses import dataclass
from datetime import datetime, timezone


# --------------------------------------------------
# Metadata
# --------------------------------------------------

@dataclass(frozen=True)
class HistoryMetadata:
    """
    History metadata.
    """

    engine_version: str

    timestamp: datetime


# --------------------------------------------------
# History Summary
# --------------------------------------------------

@dataclass(frozen=True)
class HistorySummary:
    """
    Historical Intelligence Summary.
    """

    seen_before: bool

    sample_size: int

    most_common_outcome: str

    outcome_occurrence: int

    success_rate: float

    average_duration_hours: float

    last_seen: datetime

    metadata: HistoryMetadata


# --------------------------------------------------
# Factory
# --------------------------------------------------

def create_history_summary(
    *,
    seen_before: bool,
    sample_size: int,
    most_common_outcome: str,
    outcome_occurrence: int,
    success_rate: float,
    average_duration_hours: float,
    last_seen: datetime,
) -> HistorySummary:
    """
    Create immutable HistorySummary.
    """

    return HistorySummary(

        seen_before=seen_before,

        sample_size=sample_size,

        most_common_outcome=most_common_outcome,

        outcome_occurrence=outcome_occurrence,

        success_rate=success_rate,

        average_duration_hours=average_duration_hours,

        last_seen=last_seen,

        metadata=HistoryMetadata(

            engine_version="1.0.0",

            timestamp=datetime.now(
                timezone.utc,
            ),

        ),

    )