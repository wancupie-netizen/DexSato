"""
DexSato Adaptive Experience Store.

Supabase persistence adapter for serialized
ExperienceArtifact payloads.

Responsibilities
----------------
- Save serialized Adaptive Experience payloads
- Load serialized experiences by fingerprint
- Preserve chronological history

This module does NOT:
- serialize artifacts
- deserialize artifacts
- calculate history
- build DashboardCard
- classify learning
"""

from __future__ import annotations

from scanner.database import (
    supabase,
)


TABLE_NAME = "adaptive_experiences"


# ==========================================================
# Save
# ==========================================================

def save_experience_payload(
    payload: dict,
) -> None:
    """
    Persist one serialized Experience payload.
    """

    if not isinstance(
        payload,
        dict,
    ):

        raise ValueError(
            "Experience payload must be a dictionary."
        )

    (
        supabase

        .table(
            TABLE_NAME,
        )

        .insert(
            payload,
        )

        .execute()
    )


# ==========================================================
# Load
# ==========================================================

def load_experience_payloads(
    fingerprint: str,
) -> list[dict]:
    """
    Load serialized Experience payloads by fingerprint.
    """

    normalized = fingerprint.strip()

    if not normalized:

        raise ValueError(
            "Knowledge Fingerprint is required."
        )

    response = (

        supabase

        .table(
            TABLE_NAME,
        )

        .select(
            (
                "experience_id,"
                "fingerprint,"
                "sample_size,"
                "success_count,"
                "failure_count,"
                "success_rate,"
                "last_seen,"
                "engine_version,"
                "artifact_timestamp"
            )
        )

        .eq(
            "fingerprint",
            normalized,
        )

        .order(
            "last_seen",
            desc=False,
        )

        .execute()

    )

    return list(
        response.data
        or []
    )