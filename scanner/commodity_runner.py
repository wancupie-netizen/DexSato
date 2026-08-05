"""Isolated ingestion runner for DexSato commodity markets."""

from __future__ import annotations

from scanner.commodity_registry import get_commodity_market
from scanner.database import save_market_event
from scanner.observation_builder import build_observation
from scanner.twelve_data import (
    fetch_commodity_quote,
    normalize_commodity_quote,
)


def scan_commodity_market(
    token: str,
    *,
    fetch=fetch_commodity_quote,
    save=save_market_event,
    observe=build_observation,
) -> dict:
    """Fetch, persist and observe one registered commodity."""
    market = get_commodity_market(token)
    quote = fetch(market)
    event = normalize_commodity_quote(market, quote)

    save(event)

    observation = observe(
        market["token"],
        pair_address=event["pair_address"],
    )

    return {
        "event": event,
        "provider_quote": quote,
        "observation": observation,
        "first_scan": observation is None,
    }
