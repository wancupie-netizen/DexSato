"""Server-side Public/Pro locks for premium DexSato product surfaces."""

from __future__ import annotations

from application.product_entitlement_policy import ProductEntitlementPolicy


class ProductSurfaceAccessDenied(PermissionError):
    """Raised when the resolved entitlement policy does not allow a surface."""


_CAPABILITY_FIELDS = {
    "full_discovery": "full_discovery",
    "recent_24h": "recent_24h",
    "archive": "archive",
}


def require_product_surface(
    policy: ProductEntitlementPolicy,
    capability: str,
) -> None:
    """Require one explicit premium capability from an already resolved policy."""

    if not isinstance(policy, ProductEntitlementPolicy):
        raise TypeError("policy must be a ProductEntitlementPolicy")
    field_name = _CAPABILITY_FIELDS.get(str(capability))
    if field_name is None:
        raise ValueError("unsupported product surface capability")
    if getattr(policy, field_name) is not True:
        raise ProductSurfaceAccessDenied(capability)


def locked_recent_feed() -> dict[str, object]:
    """Return a non-leaking placeholder for the Pro-only rolling Recent feed."""

    return {
        "connected": True,
        "status": "locked",
        "message": "Pro access is required for Recent 24H.",
        "rows": [],
        "eligible_count": 0,
        "market_feed": "recent_rolling_24h",
        "access_locked": True,
        "required_tier": "pro",
    }


def locked_discovery_feed(view: str = "rolling") -> dict[str, object]:
    """Return a non-leaking placeholder for the Pro-only Discovery surface."""

    selected_view = str(view or "rolling").strip() or "rolling"
    return {
        "connected": True,
        "status": "locked",
        "message": "Pro access is required for Full Discovery.",
        "candidates": [],
        "view": selected_view,
        "page": 1,
        "page_size": 25,
        "page_count": 1,
        "view_total": 0,
        "archive_total": 0,
        "qualified_total": 0,
        "access_locked": True,
        "required_tier": "pro",
    }
