"""
DexSato Market Normalizer Test
"""

from pprint import pprint

from scanner.normalizer import (
    normalize_pair,
)


print("=" * 60)
print("Market Normalizer Test")
print("=" * 60)


pair = {

    "baseToken": {

        "symbol": "BTC",

        "name": "Bitcoin",

    },

    "quoteToken": {

        "symbol": "USDT",

        "name": "Tether",

    },

    "chainId": "solana",

    "priceUsd": "80000",

    "liquidity": {

        "usd": 5000000,

    },

    "fdv": 800000000,

    "marketCap": 790000000,

    "volume": {

        "h24": 1200000,

    },

    "pairAddress": "PAIR-TEST-123",

}


event = normalize_pair(
    pair,
)

pprint(event)


# ==========================================================
# Assertions
# ==========================================================

assert event["token"] == "BTC"

assert event["name"] == "Bitcoin"

assert event["pair"] == "BTC/USDT"

assert event["pair_address"] == "PAIR-TEST-123"

assert event["chain"] == "solana"

assert event["price"] == "80000"

assert event["liquidity"] == 5000000

assert event["fdv"] == 800000000

assert event["market_cap"] == 790000000

assert event["volume_24h"] == 1200000

assert event["source"] == "DexScreener"

assert "scanned_at" in event


print("\nPASS")