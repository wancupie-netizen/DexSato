"""Registry for the DexSato commodities reference markets."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_REGISTRY_FILE = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "commodity_markets.json"
)

REQUIRED_FIELDS = (
    "token",
    "name",
    "display_pair",
    "provider",
    "provider_symbol",
    "market_id",
    "asset_class",
)


def load_commodity_registry(registry_file=None):
    """Load and validate registered commodity markets."""
    path = Path(registry_file or DEFAULT_REGISTRY_FILE)
    payload = json.loads(path.read_text(encoding="utf-8"))
    markets = payload.get("markets")

    if not isinstance(markets, list) or not markets:
        raise ValueError(
            "Commodity registry must contain a non-empty markets list."
        )

    registry = {}

    for market in markets:
        if not isinstance(market, dict):
            raise ValueError("Every commodity market must be an object.")

        missing = [
            field
            for field in REQUIRED_FIELDS
            if not str(market.get(field, "")).strip()
        ]

        if missing:
            raise ValueError(
                "Commodity market is missing fields: "
                + ", ".join(missing)
            )

        normalized = dict(market)
        normalized["token"] = str(market["token"]).strip().upper()
        token = normalized["token"]

        if token in registry:
            raise ValueError(f"Duplicate commodity market: {token}")

        registry[token] = normalized

    return registry


def get_commodity_market(token, registry_file=None):
    """Return one registered commodity or reject it."""
    normalized_token = str(token).strip().upper()
    registry = load_commodity_registry(registry_file)

    if normalized_token not in registry:
        raise ValueError(
            f"Unsupported DexSato commodity market: {normalized_token}"
        )

    return registry[normalized_token]
