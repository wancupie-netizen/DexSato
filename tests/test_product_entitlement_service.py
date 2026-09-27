from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from application.product_entitlement_policy import ProductAccessTier
from application.product_entitlement_service import (
    ProductEntitlementResolutionError,
    ProductEntitlementService,
)
from application.product_identity_models import ProductPrincipal
from application.product_subscription_models import (
    ProductSubscription,
    ProductSubscriptionPlan,
    ProductSubscriptionStatus,
)


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
USER_ID = UUID("11111111-1111-4111-8111-111111111111")
SUBSCRIPTION_ID = UUID("22222222-2222-4222-8222-222222222222")


class FakeRepository:
    def __init__(self, result=None, *, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls = []

    def get_for_user(self, *, user_id):
        self.calls.append(user_id)
        if self.error is not None:
            raise self.error
        return self.result


def _principal() -> ProductPrincipal:
    return ProductPrincipal(
        authenticated=True,
        user_id=USER_ID,
        email_masked="u***@example.com",
    )


def _subscription(
    *,
    status: ProductSubscriptionStatus = ProductSubscriptionStatus.ACTIVE,
    starts: datetime = NOW - timedelta(days=1),
    ends: datetime | None = NOW + timedelta(days=30),
) -> ProductSubscription:
    return ProductSubscription(
        id=SUBSCRIPTION_ID,
        user_id=USER_ID,
        plan_code=ProductSubscriptionPlan.FOUNDER_PRO,
        status=status,
        access_starts_at=starts,
        access_ends_at=ends,
        created_at=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(hours=1),
    )


def test_guest_resolves_public_without_subscription_lookup() -> None:
    repository = FakeRepository(result=_subscription())
    service = ProductEntitlementService(repository)

    policy = service.resolve(ProductPrincipal.guest(), now=NOW)

    assert policy.tier is ProductAccessTier.PUBLIC
    assert repository.calls == []


def test_authenticated_principal_without_user_id_fails_closed_public() -> None:
    repository = FakeRepository(result=_subscription())
    service = ProductEntitlementService(repository)

    policy = service.resolve(ProductPrincipal(authenticated=True), now=NOW)

    assert policy.tier is ProductAccessTier.PUBLIC
    assert repository.calls == []


def test_authenticated_user_without_subscription_is_public() -> None:
    repository = FakeRepository(result=None)
    service = ProductEntitlementService(repository)

    policy = service.resolve(_principal(), now=NOW)

    assert policy.tier is ProductAccessTier.PUBLIC
    assert repository.calls == [USER_ID]


@pytest.mark.parametrize(
    "status",
    [
        ProductSubscriptionStatus.INACTIVE,
        ProductSubscriptionStatus.CANCELLED,
        ProductSubscriptionStatus.EXPIRED,
    ],
)
def test_non_active_subscription_is_public(status: ProductSubscriptionStatus) -> None:
    service = ProductEntitlementService(
        FakeRepository(result=_subscription(status=status))
    )

    assert service.resolve(_principal(), now=NOW).tier is ProductAccessTier.PUBLIC


def test_active_subscription_inside_window_is_pro() -> None:
    service = ProductEntitlementService(FakeRepository(result=_subscription()))

    policy = service.resolve(_principal(), now=NOW)

    assert policy.tier is ProductAccessTier.PRO
    assert policy.full_discovery is True
    assert policy.telegram_alerts is True
    assert policy.essential_risk_warnings is True


def test_active_subscription_after_end_is_public() -> None:
    service = ProductEntitlementService(
        FakeRepository(
            result=_subscription(
                starts=NOW - timedelta(days=30),
                ends=NOW - timedelta(seconds=1),
            )
        )
    )

    assert service.resolve(_principal(), now=NOW).tier is ProductAccessTier.PUBLIC


def test_repository_failure_is_not_silently_promoted_or_downgraded() -> None:
    service = ProductEntitlementService(
        FakeRepository(error=RuntimeError("subscription store unavailable"))
    )

    with pytest.raises(ProductEntitlementResolutionError):
        service.resolve(_principal(), now=NOW)


def test_authenticated_resolution_requires_timezone_aware_now() -> None:
    service = ProductEntitlementService(FakeRepository(result=None))

    with pytest.raises(ValueError):
        service.resolve(
            _principal(),
            now=datetime(2026, 9, 27, 12, 0),
        )
