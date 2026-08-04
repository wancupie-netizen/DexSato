"""
DexSato Experience Serializer.

Converts ExperienceArtifact into a persistence-safe payload.

Responsibilities
----------------
- Preserve the complete ExperienceArtifact contract
- Convert datetime values into ISO 8601 strings
- Produce a Supabase-safe dictionary

This module does NOT:
- access databases
- create experiences
- calculate history
- mutate artifacts
"""

from __future__ import annotations

from adaptive.artifacts.experience_artifact import (
    ExperienceArtifact,
)


# ==========================================================
# Serializer
# ==========================================================

def serialize_experience(
    experience: ExperienceArtifact,
) -> dict:
    """
    Serialize an ExperienceArtifact.

    Parameters
    ----------
    experience
        ExperienceArtifact to serialize.

    Returns
    -------
    dict
        Persistence-safe Experience payload.
    """

    if experience is None:

        raise ValueError(
            "ExperienceArtifact is required."
        )

    return {

        "experience_id":
            experience.experience_id,

        "fingerprint":
            experience.fingerprint,

        "sample_size":
            experience.sample_size,

        "success_count":
            experience.success_count,

        "failure_count":
            experience.failure_count,

        "success_rate":
            experience.success_rate,

        "last_seen":
            experience.last_seen.isoformat(),

        "engine_version":
            experience.metadata.engine_version,

        "artifact_timestamp":
            experience.metadata.timestamp.isoformat(),

    }