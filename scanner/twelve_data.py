"""Twelve Data client and normalizer for spot metals."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv(
    dotenv_path=(
        Path(__file__).resolve().parents[1]
        / ".env"
    )
)

QUOTE_URL = "https://api.twelvedata.com/quote"


def fetch_commodity_quote(
    market,
    *,
    api_key=None,
    request_get=requests.get,
):
    """Fetch one registered reference quote from Twelve Data."""
    resolved_key = api_key or os.getenv("TWELVE_DATA_API_KEY")

    if not resolved_key:
        raise RuntimeError("TWELVE_DATA_API_KEY is not configured.")

    response = request_get(
        QUOTE_URL,
        params={
            "symbol": market["provider_symbol"],
            "apikey": resolved_key,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, dict):
        raise RuntimeError("Twelve Data returned an invalid quote payload.")

    if payload.get("status") == "error" or payload.get("code"):
        message = payload.get("message", "Unknown provider error.")
        raise RuntimeError(f"Twelve Data quote failed: {message}")

    returned_symbol = str(payload.get("symbol", "")).replace(" ", "")
    expected_symbol = str(market["provider_symbol"]).replace(" ", "")

    if returned_symbol.casefold() != expected_symbol.casefold():
        raise RuntimeError(
            f"Commodity symbol mismatch for {market['token']}."
        )

    if payload.get("close") in (None, ""):
        raise RuntimeError(
            f"Twelve Data returned no price for {market['token']}."
        )

    return payload


def normalize_commodity_quote(market, quote):
    """Convert a Twelve Data quote to a canonical Market Event."""
    return {
        "token": market["token"],
        "name": market["name"],
        "pair": market["display_pair"],
        "pair_address": market["market_id"],
        "chain": "spot-metals",
        "price": quote.get("close"),
        "liquidity": None,
        "fdv": None,
        "market_cap": None,
        "volume_24h": None,
        "source": "Twelve Data",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
