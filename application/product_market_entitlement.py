"""Fail-closed Public/Pro projection for ranked DexSato market feeds."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from application.product_entitlement_policy import (
    PUBLIC_ENTITLEMENTS,
    ProductEntitlementPolicy,
)
from application.product_identity_models import ProductPrincipal


class ProductEntitlementResolver(Protocol):
    def resolve(self, principal: ProductPrincipal) -> ProductEntitlementPolicy: ...


def resolve_market_entitlement_policy(
    principal: ProductPrincipal,
    *,
    service_builder: Callable[[], ProductEntitlementResolver] | None = None,
) -> ProductEntitlementPolicy:
    """Resolve market access without making public feeds depend on entitlement I/O."""

    if not isinstance(principal, ProductPrincipal):
        raise TypeError("principal must be a ProductPrincipal")

    # Guest and malformed authenticated principals are always PUBLIC and never
    # consult subscription persistence.
    if not principal.authenticated or principal.user_id is None:
        return PUBLIC_ENTITLEMENTS

    if service_builder is None:
        from application.product_identity_runtime import build_product_entitlement_service

        service_builder = build_product_entitlement_service

    try:
        policy = service_builder().resolve(principal)
    except Exception:
        # Public-capable market pages fail closed to PUBLIC when authoritative
        # entitlement state cannot be resolved. Never promote on failure.
        return PUBLIC_ENTITLEMENTS

    if not isinstance(policy, ProductEntitlementPolicy):
        return PUBLIC_ENTITLEMENTS
    return policy


def _project_feed_rows(
    feed: dict[str, object],
    *,
    max_items: int | None,
) -> dict[str, object]:
    projected = dict(feed)
    rows = feed.get("rows")
    if not isinstance(rows, list):
        return projected

    if max_items is None:
        projected["rows"] = list(rows)
        return projected

    if isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 0:
        raise ValueError("market feed max_items must be a non-negative integer or None")

    projected["rows"] = list(rows[:max_items])
    return projected


def apply_market_feed_entitlements(
    market_feeds: dict[str, dict[str, object]],
    policy: ProductEntitlementPolicy,
) -> dict[str, dict[str, object]]:
    """Project only Trending and Top Traded before market feeds reach presenters."""

    if not isinstance(market_feeds, dict):
        raise TypeError("market_feeds must be a dictionary")
    if not isinstance(policy, ProductEntitlementPolicy):
        raise TypeError("policy must be a ProductEntitlementPolicy")

    projected = dict(market_feeds)
    limits = {
        "trending": policy.trending_max_items,
        "top_traded": policy.top_traded_max_items,
    }
    for name, max_items in limits.items():
        feed = market_feeds.get(name)
        if isinstance(feed, dict):
            projected[name] = _project_feed_rows(feed, max_items=max_items)

    return projected
