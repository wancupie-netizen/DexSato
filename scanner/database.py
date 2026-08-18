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

PERSISTED_MARKET_EVENT_FIELDS = (
    "token",
    "name",
    "pair",
    "pair_address",
    "chain",
    "price",
    "liquidity",
    "fdv",
    "market_cap",
    "volume_24h",
    "source",
    "scanned_at",
)


def build_market_event_record(event):
    """Keep database writes inside the canonical market_events schema."""
    if not isinstance(event, dict):
        raise ValueError("Market Event must be a dictionary.")

    return {
        field: event[field]
        for field in PERSISTED_MARKET_EVENT_FIELDS
        if field in event
    }

def save_market_event(event):
    """
    Save a normalized Market Event.
    """

    record = build_market_event_record(event)

    response = (
        supabase
        .table("market_events")
        .insert(record)
        .execute()
    )

    return response


def get_latest_events(token, limit=2, *, pair_address=None):
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

    query = (
        supabase
        .table("market_events")
        .select("*")
        .eq("token", token)
    )

    if pair_address:
        query = query.eq("pair_address", pair_address)

    response = (
        query
        .order("scanned_at", desc=True)
        .limit(limit)
        .execute()
    )

    return response.data
