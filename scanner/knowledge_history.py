"""
DexSato Knowledge History

Read historical Intelligence Events from the database.

Responsibilities
----------------
- Load latest knowledge
- Load historical knowledge
- Count historical knowledge

This module does NOT:
- generate summaries
- detect patterns
- make decisions
- enrich intelligence
"""

from scanner.database import supabase


def get_latest(token: str):
    """
    Load the latest Intelligence Event for a token.

    Parameters
    ----------
    token : str

    Returns
    -------
    dict | None
    """

    response = (
        supabase
        .table("intelligence_events")
        .select("*")
        .eq("token", token)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


def get_history(
    token: str,
    limit: int = 50,
):
    """
    Load historical Intelligence Events.

    Parameters
    ----------
    token : str

    limit : int

    Returns
    -------
    list[dict]
    """

    response = (
        supabase
        .table("intelligence_events")
        .select("*")
        .eq("token", token)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return response.data


def count(token: str):
    """
    Count Intelligence Events for a token.

    Parameters
    ----------
    token : str

    Returns
    -------
    int
    """

    response = (
        supabase
        .table("intelligence_events")
        .select(
            "id",
            count="exact",
        )
        .eq("token", token)
        .execute()
    )

    return response.count or 0