"""
DexSato History Repository

In-memory repository for ExperienceArtifact.

Responsibilities
----------------
- Store historical experiences
- Retrieve historical experiences

This module does NOT:
- perform calculations
- build summaries
- access databases
"""

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
)


# --------------------------------------------------
# Repository
# --------------------------------------------------

_HISTORY = {}


# --------------------------------------------------
# Save
# --------------------------------------------------

def save(
    experience: ExperienceArtifact,
) -> None:
    """
    Save experience by fingerprint.
    """

    fingerprint = experience.fingerprint

    if fingerprint not in _HISTORY:

        _HISTORY[fingerprint] = []

    _HISTORY[fingerprint].append(
        experience,
    )


# --------------------------------------------------
# Find
# --------------------------------------------------

def find(
    fingerprint: str,
) -> list[ExperienceArtifact]:
    """
    Find experiences by fingerprint.
    """

    return list(

        _HISTORY.get(

            fingerprint,

            [],

        )

    )


# --------------------------------------------------
# All
# --------------------------------------------------

def all_experiences(
) -> dict[str, list[ExperienceArtifact]]:
    """
    Return repository.
    """

    return dict(
        _HISTORY,
    )


# --------------------------------------------------
# Clear
# --------------------------------------------------

def clear() -> None:
    """
    Clear repository.
    """

    _HISTORY.clear()