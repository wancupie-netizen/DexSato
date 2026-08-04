"""
DexSato Database

Shared database connection and market event persistence.

Responsibilities
----------------
- Create shared Supabase client
- Save Market Events
- Load latest Market Events

This module does NOT:
- store Intelligence Packages
- detect signals
- make decisions
"""

import os

from dotenv import load_dotenv
from supabase import create_client


# --------------------------------------------------
# Environment
# --------------------------------------------------

load_dotenv()


# --------------------------------------------------
# Shared Supabase Client
# --------------------------------------------------

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"),
)


# --------------------------------------------------
# Market Event Persistence
# --------------------------------------------------

def save_market_event(event):
    """
    Save a normalized Market Event.
    """

    response = (
        supabase
        .table("market_events")
        .insert(event)
        .execute()
    )

    return response


def get_latest_events(token, limit=2):
    """
    Load the latest Market Events for a token.

    Parameters
    ----------
    token : str

    limit : int
        Number of latest events to retrieve.

    Returns
    -------
    list
    """

    response = (
        supabase
        .table("market_events")
        .select("*")
        .eq("token", token)
        .order("scanned_at", desc=True)
        .limit(limit)
        .execute()
    )

    return response.data