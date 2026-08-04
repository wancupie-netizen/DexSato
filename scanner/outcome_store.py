"""
DexSato Outcome Store

Persist and retrieve Outcome Artifacts.

Responsibilities
----------------
- Save OutcomeArtifact
- Load latest OutcomeArtifact
- Contain no business logic
- Contain no DTO mapping

This module does NOT:
- deserialize objects
- build Product payloads
- evaluate outcomes
"""

from scanner.database import supabase


# ==========================================================
# Save
# ==========================================================

def save_outcome(
    payload: dict,
) -> None:
    """
    Persist a serialized OutcomeArtifact.

    Parameters
    ----------
    payload : dict
    """

    (
        supabase

        .table("outcome_events")

        .insert(payload)

        .execute()
    )


# ==========================================================
# Load
# ==========================================================

def load_latest_outcome(
    token: str,
) -> dict | None:
    """
    Load the latest OutcomeArtifact.

    Parameters
    ----------
    token : str

    Returns
    -------
    dict | None
    """

    response = (

        supabase

        .table("outcome_events")

        .select("*")

        .eq(
            "token",
            token,
        )

        .order(
            "created_at",
            desc=True,
        )

        .limit(1)

        .execute()

    )

    if not response.data:

        return None

    return response.data[0]