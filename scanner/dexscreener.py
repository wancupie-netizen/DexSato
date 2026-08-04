"""DexScreener exact-pair client with contract validation."""

import requests

PAIR_URL = "https://api.dexscreener.com/latest/dex/pairs/{chain_id}/{pair_address}"


def _same(value, expected):
    return str(value).strip().casefold() == str(expected).strip().casefold()


def fetch_registered_pair(market, request_get=requests.get):
    """Fetch one exact pool and reject unexpected identities."""
    url = PAIR_URL.format(chain_id=market["chain_id"], pair_address=market["pair_address"])
    response = request_get(url, timeout=15)
    response.raise_for_status()
    payload = response.json()
    pairs = payload.get("pairs", []) if isinstance(payload, dict) else payload
    selected = next((pair for pair in (pairs or []) if _same(pair.get("chainId"), market["chain_id"]) and _same(pair.get("pairAddress"), market["pair_address"])), None)
    if selected is None:
        raise RuntimeError(f"Registered pair not returned for {market['token']}.")

    checks = (
        ("dexId", selected.get("dexId"), market["dex_id"]),
        ("baseToken.address", selected.get("baseToken", {}).get("address"), market["base_address"]),
        ("quoteToken.address", selected.get("quoteToken", {}).get("address"), market["quote_address"]),
    )
    mismatches = [name for name, actual, expected in checks if not _same(actual, expected)]
    if mismatches:
        raise RuntimeError(f"Pair identity mismatch for {market['token']}: " + ", ".join(mismatches))
    return selected
