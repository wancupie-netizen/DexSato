"""
DexSato Market Store

Persist and retrieve Market Events.

Responsibilities
----------------
- Load latest Market Event
- Contain no business logic
- Contain no DTO mapping

This module does NOT:
- deserialize objects
- serialize objects
- build headers
"""

from scanner.database import supabase


def load_latest_market_event(
    token: str,
):
    """
    Load the latest Market Event.

    Parameters
    ----------
    token : str

    Returns
    -------
    dict | None
    """

    response = (

        supabase

        .table("market_events")

        .select("*")

        .eq(
            "token",
            token,
        )

        .order(
            "scanned_at",
            desc=True,
        )

        .limit(1)

        .execute()

    )

    if not response.data:

        return None

    return response.data[0]