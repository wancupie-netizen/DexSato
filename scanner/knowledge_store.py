"""
DexSato Knowledge Store

Persist and retrieve Knowledge Artifacts.

Responsibilities
----------------
- Save KnowledgeArtifact
- Load latest KnowledgeArtifact
- Contain no business logic
- Contain no DTO mapping

This module does NOT:
- deserialize objects
- build Product payloads
- evaluate knowledge
"""

from scanner.database import supabase


# ==========================================================
# Save
# ==========================================================

def save_knowledge(
    payload: dict,
) -> None:
    """
    Persist a serialized KnowledgeArtifact.

    Parameters
    ----------
    payload : dict
    """

    (
        supabase

        .table("knowledge_events")

        .insert(payload)

        .execute()
    )


# ==========================================================
# Load
# ==========================================================

def load_latest_knowledge(
    token: str,
) -> dict | None:
    """
    Load the latest KnowledgeArtifact.

    Parameters
    ----------
    token : str

    Returns
    -------
    dict | None
    """

    response = (

        supabase

        .table("knowledge_events")

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