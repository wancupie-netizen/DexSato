"""
DexSato Experience Repository

In-memory repository for ExperienceArtifacts.

Responsibilities
----------------
- Save ExperienceArtifact
- Load ExperienceArtifact
- Clear repository

This module does NOT:
- access databases
- compile learning
- merge experience
- calculate statistics
- build recommendations
"""

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
)


# --------------------------------------------------
# Memory Store
# --------------------------------------------------

_experience_store = {}


# --------------------------------------------------
# Save
# --------------------------------------------------

def save_experience(
    experience: ExperienceArtifact,
) -> None:
    """
    Save an ExperienceArtifact into memory.
    """

    _experience_store[
        experience.fingerprint
    ] = experience


# --------------------------------------------------
# Load
# --------------------------------------------------

def load_experience(
    fingerprint: str,
) -> ExperienceArtifact | None:
    """
    Load an ExperienceArtifact by fingerprint.
    """

    return _experience_store.get(
        fingerprint,
    )


# --------------------------------------------------
# Exists
# --------------------------------------------------

def experience_exists(
    fingerprint: str,
) -> bool:
    """
    Check whether an Experience exists.
    """

    return fingerprint in _experience_store


# --------------------------------------------------
# Clear
# --------------------------------------------------

def clear_repository() -> None:
    """
    Clear the repository.
    """

    _experience_store.clear()


# --------------------------------------------------
# Count
# --------------------------------------------------

def repository_size() -> int:
    """
    Return repository size.
    """

    return len(
        _experience_store,
    )