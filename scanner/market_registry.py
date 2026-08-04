"""Exact market registry for the DexSato production universe."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_REGISTRY_FILE = Path(__file__).resolve().parents[1] / "config" / "market_pairs.json"
REQUIRED_FIELDS = ("token", "display_pair", "chain_id", "dex_id", "pair_address", "base_address", "quote_address")


def load_market_registry(registry_file=None):
    """Load and validate the exact-pair production registry."""
    path = Path(registry_file or DEFAULT_REGISTRY_FILE)
    payload = json.loads(path.read_text(encoding="utf-8"))
    markets = payload.get("markets")
    if not isinstance(markets, list) or not markets:
        raise ValueError("Market registry must contain a non-empty markets list.")

    registry = {}
    for market in markets:
        if not isinstance(market, dict):
            raise ValueError("Every registered market must be an object.")
        missing = [field for field in REQUIRED_FIELDS if not str(market.get(field, "")).strip()]
        if missing:
            raise ValueError(f"Registered market is missing fields: {', '.join(missing)}")
        normalized = dict(market)
        normalized["token"] = str(market["token"]).strip().upper()
        token = normalized["token"]
        if token in registry:
            raise ValueError(f"Duplicate registered market: {token}")
        registry[token] = normalized
    return registry


def get_market(token, registry_file=None):
    """Return one registered market or reject unsupported symbols."""
    normalized_token = str(token).strip().upper()
    registry = load_market_registry(registry_file)
    if normalized_token not in registry:
        raise ValueError(f"Unsupported DexSato market: {normalized_token}")
    return registry[normalized_token]
