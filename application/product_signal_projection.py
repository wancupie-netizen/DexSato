"""Pure detected-signal projection for entitlement-safe market feeds."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from application.product_signal_entitlement import ProductSignalEntitlementAdmission


DETECTED_SIGNAL_FEED_ORDER = (
    "trending",
    "top_traded",
    "organic_flow",
    "recent",
)


def _detected_signal_is_active(value: object) -> bool:
    if isinstance(value, dict):
        return bool(str(value.get("primary_signal") or "").strip())
    if not value:
        return False
    return bool(str(value).strip())


def _valid_token_address(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    token_address = value.strip()
    if (
        not token_address
        or token_address != value
        or any(character.isspace() for character in token_address)
        or len(token_address) > 128
    ):
        return None
    return token_address


def _ordered_feed_names(market_feeds: Mapping[str, object]) -> tuple[str, ...]:
    canonical = [name for name in DETECTED_SIGNAL_FEED_ORDER if name in market_feeds]
    extras = sorted(
        name
        for name in market_feeds
        if isinstance(name, str) and name not in DETECTED_SIGNAL_FEED_ORDER
    )
    return tuple(canonical + extras)


def collect_detected_signal_token_addresses(
    market_feeds: Mapping[str, object],
) -> tuple[str, ...]:
    """Collect unique visible signal tokens in deterministic market-view order."""

    if not isinstance(market_feeds, Mapping):
        raise TypeError("market_feeds must be a mapping")

    ordered: list[str] = []
    seen: set[str] = set()

    for feed_name in _ordered_feed_names(market_feeds):
        payload = market_feeds.get(feed_name)
        if not isinstance(payload, dict):
            continue
        rows = payload.get("rows")
        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            if not _detected_signal_is_active(row.get("detected_signal")):
                continue
            token_address = _valid_token_address(row.get("token_address"))
            if token_address is None or token_address in seen:
                continue
            seen.add(token_address)
            ordered.append(token_address)

    return tuple(ordered)


def project_detected_signal_entitlements(
    market_feeds: Mapping[str, object],
    admission: ProductSignalEntitlementAdmission,
) -> dict[str, object]:
    """Hide non-admitted signals without changing market rows, order, or metadata."""

    if not isinstance(market_feeds, Mapping):
        raise TypeError("market_feeds must be a mapping")
    if not isinstance(admission, ProductSignalEntitlementAdmission):
        raise TypeError("admission must be a ProductSignalEntitlementAdmission")

    allowed = frozenset(admission.allowed_token_addresses)
    projected: dict[str, object] = {}

    for feed_name, payload in market_feeds.items():
        if not isinstance(payload, dict):
            projected[feed_name] = payload
            continue

        rows = payload.get("rows")
        if not isinstance(rows, list):
            projected[feed_name] = payload
            continue

        projected_rows: list[Any] = []
        changed = False

        for row in rows:
            if not isinstance(row, dict):
                projected_rows.append(row)
                continue

            signal = row.get("detected_signal")
            if not _detected_signal_is_active(signal):
                projected_rows.append(row)
                continue

            token_address = _valid_token_address(row.get("token_address"))
            if token_address is not None and token_address in allowed:
                projected_rows.append(row)
                continue

            hidden = dict(row)
            hidden.pop("detected_signal", None)
            projected_rows.append(hidden)
            changed = True

        if not changed:
            projected[feed_name] = payload
            continue

        feed_copy = dict(payload)
        feed_copy["rows"] = projected_rows
        projected[feed_name] = feed_copy

    return projected
