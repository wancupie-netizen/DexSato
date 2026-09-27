"""Provider-neutral Public/Pro entitlement policy for DexSato product access."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from application.product_identity_models import ProductPrincipal


class ProductAccessTier(str, Enum):
    """Customer-facing access tiers. Authentication is intentionally separate."""

    PUBLIC = "public"
    PRO = "pro"


@dataclass(frozen=True, slots=True)
class ProductEntitlementPolicy:
    """Server-side access policy resolved independently from authentication."""

    tier: ProductAccessTier
    trending_max_items: int | None
    top_traded_max_items: int | None
    detected_signals_unique_rolling_24h_max: int | None
    full_discovery: bool
    recent_24h: bool
    archive: bool
    full_context_history: bool
    telegram_alerts: bool
    essential_risk_warnings: bool


PUBLIC_ENTITLEMENTS = ProductEntitlementPolicy(
    tier=ProductAccessTier.PUBLIC,
    trending_max_items=25,
    top_traded_max_items=25,
    detected_signals_unique_rolling_24h_max=5,
    full_discovery=False,
    recent_24h=False,
    archive=False,
    full_context_history=False,
    telegram_alerts=False,
    essential_risk_warnings=True,
)

PRO_ENTITLEMENTS = ProductEntitlementPolicy(
    tier=ProductAccessTier.PRO,
    trending_max_items=None,
    top_traded_max_items=None,
    detected_signals_unique_rolling_24h_max=None,
    full_discovery=True,
    recent_24h=True,
    archive=True,
    full_context_history=True,
    telegram_alerts=True,
    essential_risk_warnings=True,
)


def resolve_product_entitlements(
    principal: ProductPrincipal,
    *,
    subscription_active: bool,
) -> ProductEntitlementPolicy:
    """Resolve access fail-closed: only an authenticated active subscriber is Pro."""

    if not isinstance(subscription_active, bool):
        raise TypeError("subscription_active must be a boolean")
    if principal.authenticated and subscription_active:
        return PRO_ENTITLEMENTS
    return PUBLIC_ENTITLEMENTS
