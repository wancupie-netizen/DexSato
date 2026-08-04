"""
DexSato Intelligence Store

Persist and retrieve serialized Intelligence Packages.

Responsibilities
----------------
- Save serialized Intelligence Packages
- Load latest stored Intelligence Package

This module does NOT:
- serialize artifacts
- deserialize artifacts
- build fingerprints
- detect signals
- interpret markets
- make decisions
"""

from scanner.database import supabase


# ==========================================================
# Save
# ==========================================================

def save_intelligence(
    payload: dict,
) -> None:
    """
    Persist a serialized Intelligence Package.

    Parameters
    ----------
    payload : dict
    """

    (
        supabase

        .table("intelligence_events")

        .insert(payload)

        .execute()
    )


# ==========================================================
# Load
# ==========================================================

def load_latest_intelligence(
    token: str,
) -> dict | None:
    """
    Load the latest serialized Intelligence Package.

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

        .select("intelligence_package")

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

    return response.data[0][
        "intelligence_package"
    ]