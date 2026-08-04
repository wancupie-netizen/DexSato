"""
DexSato Observation Builder

Build market observations by comparing market events.

Responsibilities
----------------
- Load latest market events
- Calculate percentage changes
- Produce a normalized observation

This module does NOT:
- detect signals
- interpret market behaviour
- make decisions
"""

from scanner.database import get_latest_events


def percent_change(current, previous):
    """
    Calculate percentage change between two values.

    Returns
    -------
    float | None
    """

    if current is None or previous is None:
        return None

    if previous == 0:
        return None

    return round(((current - previous) / previous) * 100, 4)


def calculate_observation(
    token: str,
    current: dict,
    previous: dict,
):
    """
    Build an observation from two market events.

    Parameters
    ----------
    token : str

    current : dict

    previous : dict

    Returns
    -------
    dict
    """

    return {

        "token": token,

        "price_change_pct": percent_change(
            current["price"],
            previous["price"],
        ),

        "liquidity_change_pct": percent_change(
            current["liquidity"],
            previous["liquidity"],
        ),

        "volume_change_pct": percent_change(
            current["volume_24h"],
            previous["volume_24h"],
        ),

        "market_cap_change_pct": percent_change(
            current["market_cap"],
            previous["market_cap"],
        ),

        "fdv_change_pct": percent_change(
            current["fdv"],
            previous["fdv"],
        ),
    }


def build_observation(token, *, pair_address=None):
    """
    Build an observation from the latest two market events.
    """

    events = get_latest_events(token, pair_address=pair_address)

    if len(events) < 2:
        return None

    return calculate_observation(
        token,
        events[0],
        events[1],
    )
