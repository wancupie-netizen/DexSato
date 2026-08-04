"""
DexSato Market Snapshot Builder Test
"""

from pprint import pprint

from scanner.market_snapshot_builder import (
    build_market_snapshot,
)


print("=" * 60)
print("Market Snapshot Builder Test")
print("=" * 60)


event = {

    "token": "BTC",

    "name": "Bitcoin",

    "pair": "BTC/USDT",

    "pair_address": "PAIR-123",

    "chain": "solana",

    "price": "80000",

    "liquidity": 5000000,

    "fdv": 800000000,

    "market_cap": 790000000,

    "volume_24h": 1200000,

    "source": "DexScreener",

    "scanned_at": "2026-07-17T00:00:00",

}


snapshot = build_market_snapshot(
    event,
)

print(snapshot)


# ==========================================================
# Assertions
# ==========================================================

assert snapshot.symbol == "BTC"

assert snapshot.pair == "BTC/USDT"

assert snapshot.chain == "solana"

assert str(snapshot.price) == "80000"

assert str(snapshot.liquidity) == "5000000"

assert str(snapshot.volume_24h) == "1200000"

assert str(snapshot.fdv) == "800000000"

assert str(snapshot.market_cap) == "790000000"

assert snapshot.provider == "DexScreener"

assert snapshot.snapshot_id is not None

assert snapshot.captured_at is not None


print("\nPASS")