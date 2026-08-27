"""Bounded exact-pool market enrichment for Solana Discovery candidates."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import math
from threading import Lock
from time import monotonic
from typing import Any, Callable

import requests


PAIR_URL = "https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
MIN_LIQUIDITY_USD = 5_000.0
MIN_VOLUME_24H_USD = 1_000.0
MAX_CANDIDATES_CHECKED = 12
MI_V40_ROTATING_ENRICHMENT = True
_ENRICHMENT_CURSOR = 0
_ENRICHMENT_CURSOR_LOCK = Lock()
MAX_PUBLIC_CANDIDATES = 8
CACHE_SECONDS = 75
REQUEST_TIMEOUT_SECONDS = 6
_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}
_CACHE_LOCK = Lock()


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


# COIN_LIST_CHANGE_V282_SIGNED_24H_CHANGE
def _signed_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _same(value: Any, expected: Any) -> bool:
    return str(value or "").strip() == str(expected or "").strip()


# TOKEN_WORKSPACE_V2451_EXACT_PAIR_AGE_SOURCE_FIX
def _pair_age_hours(created_at: Any, now: datetime) -> float | None:
    try:
        created = datetime.fromtimestamp(float(created_at) / 1000, tz=timezone.utc)
        seconds = max(0.0, (now - created).total_seconds())
    except (TypeError, ValueError, OSError, OverflowError):
        return None
    return seconds / 3600.0


def _pair_age_label(created_at: Any, now: datetime) -> str:
    hours = _pair_age_hours(created_at, now)
    if hours is None:
        return "Unavailable"
    total_minutes = max(0, int(hours * 60))
    if total_minutes < 1:
        return "<1m"
    if total_minutes < 60:
        return f"{total_minutes}m"
    total_hours, minutes = divmod(total_minutes, 60)
    if total_hours < 24:
        return f"{total_hours}h {minutes}m" if minutes else f"{total_hours}h"
    days, hours_left = divmod(total_hours, 24)
    return f"{days}d {hours_left}h" if hours_left else f"{days}d"


def _cached_pair(
    pair_address: str,
    request_get: Callable[..., Any],
) -> dict[str, Any] | None:
    current = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(pair_address)
        if cached and current - cached[0] < CACHE_SECONDS:
            return cached[1]
    try:
        response = request_get(
            PAIR_URL.format(pair_address=pair_address),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
        result = next((item for item in pairs if isinstance(item, dict) and _same(item.get("pairAddress"), pair_address)), None)
    except (requests.RequestException, ValueError, TypeError, StopIteration):
        result = None
    with _CACHE_LOCK:
        _CACHE[pair_address] = (current, result)
    return result


def qualify_candidate(
    observed: dict[str, Any],
    pair: dict[str, Any] | None,
    *,
    now: datetime,
    diagnostic: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Reject ambiguous identities, missing market evidence and weak activity."""
    def reject(code: str, title: str, message: str) -> None:
        if diagnostic is not None:
            diagnostic.update({"evaluated": True, "qualified": False, "code": code, "title": title, "message": message})

    if not isinstance(pair, dict):
        reject("provider_unavailable", "Market verification unavailable", "The exact-pool provider did not return a usable response in this scan.")
        return None
    token_address = str(observed.get("token_address") or "").strip()
    pair_address = str(observed.get("pair_address") or "").strip()
    base = pair.get("baseToken") if isinstance(pair.get("baseToken"), dict) else {}
    quote = pair.get("quoteToken") if isinstance(pair.get("quoteToken"), dict) else {}
    if not token_address or not pair_address:
        reject("identity_unresolved", "Token identity unresolved", "A token mint and exact pair address are both required.")
        return None
    if pair.get("chainId") != "solana":
        reject("wrong_network", "Solana identity check failed", "The provider did not identify this exact pool as Solana.")
        return None
    if not _same(pair.get("pairAddress"), pair_address):
        reject("pair_mismatch", "Exact-pool match failed", "The provider pair address did not match the observed pair.")
        return None
    if not _same(base.get("address"), token_address):
        reject("token_mismatch", "Token identity mismatch", "The provider base-token mint did not match the observed token.")
        return None
    liquidity = _number((pair.get("liquidity") or {}).get("usd"))
    volume = _number((pair.get("volume") or {}).get("h24"))
    price = _number(pair.get("priceUsd"))
    change_24h = _signed_number((pair.get("priceChange") or {}).get("h24"))
    txns = pair.get("txns") if isinstance(pair.get("txns"), dict) else {}
    h24_txns = txns.get("h24") if isinstance(txns.get("h24"), dict) else {}
    buys_24h = _number(h24_txns.get("buys"))
    sells_24h = _number(h24_txns.get("sells"))
    if liquidity is None or volume is None or price is None:
        missing = ", ".join(name for name, value in (("price", price), ("liquidity", liquidity), ("24h volume", volume)) if value is None)
        reject("market_data_incomplete", "Market data incomplete", f"The provider did not supply valid {missing} data in this scan.")
        return None
    if liquidity < MIN_LIQUIDITY_USD:
        reject("liquidity_below_threshold", "Liquidity below qualification threshold", f"Observed liquidity ${liquidity:,.2f} is below the required ${MIN_LIQUIDITY_USD:,.2f}.")
        return None
    if volume < MIN_VOLUME_24H_USD:
        reject("volume_below_threshold", "24h activity below qualification threshold", f"Observed 24h volume ${volume:,.2f} is below the required ${MIN_VOLUME_24H_USD:,.2f}.")
        return None
    if diagnostic is not None:
        diagnostic.update({"evaluated": True, "qualified": True, "code": "qualified", "title": "Qualified now", "message": "Current identity, exact-pool, liquidity and 24h activity checks passed."})
    return {
        "token_address": token_address,
        "pair_address": pair_address,
        "symbol": str(base.get("symbol") or observed.get("symbol") or "Unknown"),
        "name": str(base.get("name") or observed.get("name") or "Unknown token"),
        "quote_symbol": str(quote.get("symbol") or "Unknown"),
        "dex_id": str(pair.get("dexId") or "Unknown"),
        "price_usd": price,
        "change_24h": change_24h,
        "liquidity_usd": liquidity,
        "volume_24h_usd": volume,
        "txns_24h": (
            int(buys_24h + sells_24h)
            if buys_24h is not None and sells_24h is not None
            else None
        ),
        "pair_age": _pair_age_label(pair.get("pairCreatedAt"), now),
        "pair_age_hours": _pair_age_hours(pair.get("pairCreatedAt"), now),
        "evidence": "Verified Solana pool with observable liquidity and 24h activity.",
        "risk_label": "Token security not independently verified",
        "source": "DexScreener exact pair",
        "source_url": str(pair.get("url") or ""),
        "last_seen_at": str(observed.get("last_seen_at") or ""),
    }


def qualify_discovery_candidates(
    candidates: dict[str, Any],
    *,
    now: datetime,
    request_get: Callable[..., Any] = requests.get,
    diagnostics: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Enrich only a bounded, newest-first set of unique resolved pools."""
    resolved = [item for item in candidates.values() if isinstance(item, dict) and item.get("token_address") and item.get("pair_address")]
    resolved.sort(key=lambda item: str(item.get("last_seen_at") or ""), reverse=True)



    # MI v4.0: deduplicate the whole resolved universe first, then rotate the

    # bounded enrichment window.  This preserves the existing API budget while

    # preventing older pools from being permanently starved by newer arrivals.

    unique_resolved: list[dict[str, Any]] = []

    seen_tokens: set[str] = set()

    seen_pairs: set[str] = set()

    for item in resolved:

        token = str(item["token_address"])

        pool = str(item["pair_address"])

        if token in seen_tokens or pool in seen_pairs:

            continue

        seen_tokens.add(token)

        seen_pairs.add(pool)

        unique_resolved.append(item)



    selected: list[dict[str, Any]] = []

    if unique_resolved:

        global _ENRICHMENT_CURSOR

        with _ENRICHMENT_CURSOR_LOCK:

            start = _ENRICHMENT_CURSOR % len(unique_resolved)

            take = min(MAX_CANDIDATES_CHECKED, len(unique_resolved))

            selected = [

                unique_resolved[(start + offset) % len(unique_resolved)]

                for offset in range(take)

            ]

            _ENRICHMENT_CURSOR = (start + take) % len(unique_resolved)
    if diagnostics is not None:
        for item in unique_resolved:
            token = str(item["token_address"])
            diagnostics[token] = {
                "evaluated": False,
                "qualified": False,
                "code": "not_evaluated_scan",
                "title": "Not evaluated in this scan",
                "message": "The bounded rotating scan did not select this token in the current cycle.",
            }
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(selected)))) as executor:
        futures = {executor.submit(_cached_pair, str(item["pair_address"]), request_get): item for item in selected}
        for future in as_completed(futures):
            observed = futures[future]
            token = str(observed.get("token_address") or "")
            diagnostic = diagnostics.setdefault(token, {}) if diagnostics is not None else None
            try:
                qualified = qualify_candidate(observed, future.result(), now=now, diagnostic=diagnostic)
            except Exception:
                if diagnostic is not None:
                    diagnostic.update({"evaluated": True, "qualified": False, "code": "verification_error", "title": "Market verification unavailable", "message": "The qualification check could not be completed in this scan."})
                continue
            if qualified is not None:
                results.append(qualified)
    results.sort(key=lambda item: (item["last_seen_at"], item["volume_24h_usd"]), reverse=True)
    if diagnostics is not None:
        for item in results[MAX_PUBLIC_CANDIDATES:]:
            diagnostics[str(item["token_address"])] = {
                "evaluated": True,
                "qualified": False,
                "code": "outside_public_limit",
                "title": "Outside current public result limit",
                "message": "The token passed the checks but ranked outside the bounded public result for this cycle.",
            }
    return results[:MAX_PUBLIC_CANDIDATES]
