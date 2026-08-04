"""
DexSato History Builder

Build HistorySummary from ExperienceArtifact collection.

Responsibilities
----------------
- Summarise historical experience
- Produce immutable HistorySummary

This module does NOT:
- access databases
- access repositories
- perform predictions
- perform AI analysis
"""

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
)

from adaptive.history.history_summary import (
    HistorySummary,
    create_history_summary,
)


# --------------------------------------------------
# Build
# --------------------------------------------------

def build_history_summary(
    experiences: list[ExperienceArtifact],
) -> HistorySummary:
    """
    Build HistorySummary from historical experiences.
    """

    if not experiences:

        return create_history_summary(

            seen_before=False,

            sample_size=0,

            most_common_outcome="UNKNOWN",

            outcome_occurrence=0,

            success_rate=0.0,

            average_duration_hours=0.0,

            last_seen=None,

        )

    sample_size = len(
        experiences,
    )

    success_count = sum(

        experience.success_count

        for experience in experiences

    )

    success_rate = (

        success_count

        / sample_size

    ) * 100.0

    most_common_outcome = "SUCCESS"

    outcome_occurrence = success_count

    last_seen = max(

        experience.last_seen

        for experience in experiences

    )

    return create_history_summary(

        seen_before=True,

        sample_size=sample_size,

        most_common_outcome=most_common_outcome,

        outcome_occurrence=outcome_occurrence,

        success_rate=round(

            success_rate,

            2,

        ),

        average_duration_hours=0.0,

        last_seen=last_seen,

    )