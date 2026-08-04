"""
DexSato CoinMarketCap Universe.

Loads the current Top 100 cryptocurrencies ranked by
market capitalisation.

Responsibilities
----------------
- Fetch the CoinMarketCap Top 100 list
- Preserve CoinMarketCap ranking order
- Cache the list for twenty-four hours
- Return normalized token symbols

Environment variables
---------------------
COINMARKETCAP_API_KEY

This module does NOT:
- run DexSato scans
- render dashboards
- send Telegram alerts
- schedule universe refreshes
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


COINMARKETCAP_LISTINGS_URL = (
    "https://pro-api.coinmarketcap.com/"
    "v1/cryptocurrency/listings/latest"
)

UNIVERSE_LIMIT = 100

UNIVERSE_CACHE_DURATION = timedelta(
    hours=24,
)

UNIVERSE_CACHE_FILE = Path(
    "output",
    "cache",
    "coinmarketcap_top100.json",
)


# ==========================================================
# Cache
# ==========================================================

def read_cached_universe(
    *,
    cache_file: Path = UNIVERSE_CACHE_FILE,
    now: datetime | None = None,
) -> tuple[str, ...] | None:
    """
    Return a fresh cached universe when available.
    """

    if not cache_file.exists():

        return None

    try:

        payload = json.loads(
            cache_file.read_text(
                encoding="utf-8",
            )
        )

        fetched_at = datetime.fromisoformat(
            payload["fetched_at"],
        )

        tokens = payload["tokens"]

    except (
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):

        return None

    if fetched_at.tzinfo is None:

        return None

    resolved_now = (
        now
        or datetime.now(
            timezone.utc,
        )
    )

    if (
        resolved_now
        - fetched_at
        >= UNIVERSE_CACHE_DURATION
    ):

        return None

    if not isinstance(
        tokens,
        list,
    ):

        return None

    normalized_tokens = tuple(
        str(token).strip().upper()
        for token in tokens
        if str(token).strip()
    )

    if not normalized_tokens:

        return None

    return normalized_tokens


def write_cached_universe(
    *,
    tokens: tuple[str, ...],
    cache_file: Path = UNIVERSE_CACHE_FILE,
    fetched_at: datetime | None = None,
) -> None:
    """
    Save the current ranked universe to disk.
    """

    resolved_fetched_at = (
        fetched_at
        or datetime.now(
            timezone.utc,
        )
    )

    cache_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "fetched_at": (
            resolved_fetched_at.isoformat()
        ),
        "tokens": list(
            tokens,
        ),
    }

    cache_file.write_text(
        json.dumps(
            payload,
            indent=2,
        ),
        encoding="utf-8",
    )


# ==========================================================
# CoinMarketCap Fetch
# ==========================================================

def fetch_coinmarketcap_top_100(
    *,
    api_key: str | None = None,
    get: Callable[..., object] = requests.get,
    cache_file: Path = UNIVERSE_CACHE_FILE,
) -> tuple[str, ...]:
    """
    Fetch and cache the CoinMarketCap Top 100 symbols.
    """

    load_dotenv()

    resolved_api_key = (
        api_key
        or os.getenv(
            "COINMARKETCAP_API_KEY",
        )
    )

    if not resolved_api_key:

        raise RuntimeError(
            "COINMARKETCAP_API_KEY is not configured."
        )

    response = get(
        COINMARKETCAP_LISTINGS_URL,
        headers={
            "Accept": "application/json",
            "X-CMC_PRO_API_KEY": resolved_api_key,
        },
        params={
            "start": 1,
            "limit": UNIVERSE_LIMIT,
            "convert": "USD",
        },
        timeout=20,
    )

    response.raise_for_status()

    payload = response.json()

    data = payload.get(
        "data",
    )

    if not isinstance(
        data,
        list,
    ):

        raise RuntimeError(
            "CoinMarketCap returned an invalid listings payload."
        )

    tokens: list[str] = []

    seen: set[str] = set()

    for item in data:

        if not isinstance(
            item,
            dict,
        ):

            continue

        symbol = str(
            item.get(
                "symbol",
                "",
            )
        ).strip().upper()

        if not symbol:

            continue

        if symbol in seen:

            continue

        seen.add(
            symbol,
        )

        tokens.append(
            symbol,
        )

        if len(
            tokens,
        ) >= UNIVERSE_LIMIT:

            break

    if not tokens:

        raise RuntimeError(
            "CoinMarketCap returned no usable token symbols."
        )

    universe = tuple(
        tokens,
    )

    write_cached_universe(
        tokens=universe,
        cache_file=cache_file,
    )

    return universe


# ==========================================================
# Public Universe Loader
# ==========================================================

def load_top_100_universe(
    *,
    api_key: str | None = None,
    cache_file: Path = UNIVERSE_CACHE_FILE,
    now: datetime | None = None,
    get: Callable[..., object] = requests.get,
) -> tuple[str, ...]:
    """
    Return the daily Top 100 CoinMarketCap universe.

    A fresh cache is preferred. CoinMarketCap is contacted
    only when the cache is missing or older than 24 hours.
    """

    cached = read_cached_universe(
        cache_file=cache_file,
        now=now,
    )

    if cached is not None:

        return cached

    return fetch_coinmarketcap_top_100(
        api_key=api_key,
        get=get,
        cache_file=cache_file,
    )