"""
DexSato Market Normalizer

Normalize raw DexScreener pair data into a
canonical Market Event.

Responsibilities
----------------
- Normalize provider payload
- Produce canonical Market Event
- Remain provider-specific

This module does NOT:
- perform analysis
- build domain models
- access databases
"""

from datetime import datetime, timezone


def normalize_pair(pair: dict, *, token: str | None = None, display_pair: str | None = None) -> dict:
    """
    Normalize a DexScreener pair into
    DexSato Market Event.
    """

    base = pair["baseToken"]

    quote = pair["quoteToken"]

    return {

        "token":
            token or base["symbol"],

        "name":
            base["name"],

        "pair":
            display_pair or f"{base['symbol']}/{quote['symbol']}",

        "pair_address":
            pair.get("pairAddress"),

        "chain":
            pair["chainId"],

        "price":
            pair.get("priceUsd"),

        "liquidity":
            pair.get(
                "liquidity",
                {},
            ).get("usd"),

        "fdv":
            pair.get("fdv"),

        "market_cap":
            pair.get("marketCap"),

        "volume_24h":
            pair.get(
                "volume",
                {},
            ).get("h24"),

        "source":
            "DexScreener",

        "scanned_at":
            datetime.now(timezone.utc).isoformat(),

    }
