"""
DexSato Market Snapshot Builder

Build a Domain MarketSnapshot from a
normalized Market Event.

Responsibilities
----------------
- Convert Market Event into MarketSnapshot
- Perform domain mapping only

This module does NOT:
- access databases
- perform market analysis
- serialize objects
- access external APIs
"""

from decimal import Decimal

from core.models.market_snapshot import (
    MarketSnapshot,
)


def _decimal(value):

    if value is None:

        return None

    return Decimal(str(value))


def build_market_snapshot(
    event: dict,
) -> MarketSnapshot:
    """
    Convert a normalized Market Event
    into a Domain MarketSnapshot.
    """

    return MarketSnapshot(

        symbol=
            event["token"],

        pair=
            event["pair"],

        chain=
            event["chain"],

        price=
            _decimal(event["price"]),

        liquidity=
            _decimal(event["liquidity"]),

        volume_24h=
            _decimal(event["volume_24h"]),

        fdv=
            _decimal(event["fdv"]),

        market_cap=
            _decimal(event["market_cap"]),

        buyers_24h=
            None,

        sellers_24h=
            None,

        transactions_24h=
            None,

        provider=
            event["source"],

    )