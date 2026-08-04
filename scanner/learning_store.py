"""
DexSato Learning Store

Persist and retrieve Learning Artifacts.

Responsibilities
----------------
- Save LearningArtifact
- Load latest LearningArtifact
- Contain no business logic
- Contain no DTO mapping

This module does NOT:
- deserialize objects
- build Product payloads
- evaluate learning
"""

from scanner.database import supabase


# ==========================================================
# Save
# ==========================================================

def save_learning(
    payload: dict,
) -> None:
    """
    Persist a serialized LearningArtifact.

    Parameters
    ----------
    payload : dict
    """

    (
        supabase

        .table("learning_events")

        .insert(payload)

        .execute()
    )


# ==========================================================
# Load
# ==========================================================

def load_latest_learning(
    token: str,
) -> dict | None:
    """
    Load the latest LearningArtifact.

    Parameters
    ----------
    token : str

    Returns
    -------
    dict | None
    """

    response = (

        supabase

        .table("learning_events")

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