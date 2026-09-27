"""Resolve DexSato Public/Pro access from server-side subscription state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from application.product_entitlement_policy import (
    ProductEntitlementPolicy,
    resolve_product_entitlements,
)
from application.product_identity_models import ProductPrincipal
from application.product_subscription_models import ProductSubscription


class ProductSubscriptionReader(Protocol):
    def get_for_user(self, *, user_id: UUID) -> ProductSubscription | None: ...


class ProductEntitlementResolutionError(RuntimeError):
    """Raised when authoritative subscription state cannot be resolved."""


class ProductEntitlementService:
    def __init__(self, repository: ProductSubscriptionReader) -> None:
        if repository is None or not callable(getattr(repository, "get_for_user", None)):
            raise TypeError("a product subscription repository is required")
        self._repository = repository

    def resolve(
        self,
        principal: ProductPrincipal,
        *,
        now: datetime | None = None,
    ) -> ProductEntitlementPolicy:
        if not isinstance(principal, ProductPrincipal):
            raise TypeError("principal must be a ProductPrincipal")

        # Guest and malformed authenticated principals fail closed to PUBLIC
        # without consulting subscription persistence.
        if not principal.authenticated or principal.user_id is None:
            return resolve_product_entitlements(
                principal,
                subscription_active=False,
            )

        instant = datetime.now(UTC) if now is None else now
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        instant = instant.astimezone(UTC)

        try:
            subscription = self._repository.get_for_user(user_id=principal.user_id)
            subscription_active = (
                False if subscription is None else subscription.is_active_at(instant)
            )
        except Exception as error:
            raise ProductEntitlementResolutionError(
                "Unable to resolve authoritative product entitlement."
            ) from error

        return resolve_product_entitlements(
            principal,
            subscription_active=subscription_active,
        )
