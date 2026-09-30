"""Canonical Core 20 identity registry for DexSato Solana Universe.

This module fixes membership and display order by canonical Solana mint.
It performs no network calls, token qualification, signal calculation,
routing, Jupiter execution, or persistence.
"""

from __future__ import annotations

from typing import Final, TypedDict


class SolanaUniverseAsset(TypedDict):
    symbol: str
    name: str
    mint: str


SOLANA_UNIVERSE: Final[tuple[SolanaUniverseAsset, ...]] = (
    {"symbol": "JUP", "name": "Jupiter", "mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"},
    {"symbol": "RAY", "name": "Raydium", "mint": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"},
    {"symbol": "JTO", "name": "Jito", "mint": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL"},
    {"symbol": "PYTH", "name": "Pyth Network", "mint": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"},
    {"symbol": "KMNO", "name": "Kamino", "mint": "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS"},
    {"symbol": "ORCA", "name": "Orca", "mint": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE"},
    {"symbol": "DRIFT", "name": "Drift", "mint": "DriFtupJYLTosbwoN8koMbEYSx54aFAVLddWsbksjwg7"},
    {"symbol": "RENDER", "name": "Render", "mint": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof"},
    {"symbol": "HNT", "name": "Helium", "mint": "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux"},
    {"symbol": "GRASS", "name": "Grass", "mint": "Grass7B4RdKfBCjTKgSqnXkqjwiGvQyFbuSCUJr3XXjs"},
    {"symbol": "HONEY", "name": "Hivemapper Honey", "mint": "4vMsoUT2BWatFweudnQM1xedRLfJgJ7hswhcpz4xgBTy"},
    {"symbol": "BONK", "name": "Bonk", "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
    {"symbol": "WIF", "name": "dogwifhat", "mint": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"},
    {"symbol": "PENGU", "name": "Pudgy Penguins", "mint": "2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv"},
    {"symbol": "FARTCOIN", "name": "Fartcoin", "mint": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"},
    {"symbol": "TRUMP", "name": "Official Trump", "mint": "6p6xgHyF7AeE6TZkSmFsko444wqoP15icUSqi2jfGiPN"},
    {"symbol": "PNUT", "name": "Peanut the Squirrel", "mint": "2qEHjDLDLbuBgRYvsxhc5D6uDWAivNFZGan56P1tpump"},
    {"symbol": "MEW", "name": "cat in a dogs world", "mint": "MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5"},
    {"symbol": "BOME", "name": "BOOK OF MEME", "mint": "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82"},
    {"symbol": "GIGA", "name": "Gigachad", "mint": "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9"},
)


SOLANA_UNIVERSE_BY_MINT: Final[dict[str, SolanaUniverseAsset]] = {
    asset["mint"]: asset for asset in SOLANA_UNIVERSE
}


def solana_universe_asset(token_address: str) -> SolanaUniverseAsset | None:
    """Return one Core 20 asset by exact canonical Solana mint."""
    return SOLANA_UNIVERSE_BY_MINT.get(str(token_address or "").strip())


def is_solana_universe_asset(token_address: str) -> bool:
    """Return whether an exact mint belongs to the locked Core 20."""
    return solana_universe_asset(token_address) is not None