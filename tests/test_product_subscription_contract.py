from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from application.product_subscription_models import (
    ProductSubscription,
    ProductSubscriptionPlan,
    ProductSubscriptionStatus,
)


USER_ID = UUID("11111111-1111-4111-8111-111111111111")
SUBSCRIPTION_ID = UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


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


def _migration_text() -> str:
    migrations = sorted(
        Path("supabase/migrations").glob("*_product_subscription_entitlement.sql")
    )
    assert len(migrations) == 1
    return migrations[0].read_text(encoding="utf-8")


def test_active_subscription_is_effective_only_inside_access_window() -> None:
    subscription = _subscription()

    assert subscription.is_active_at(NOW) is True
    assert subscription.is_active_at(subscription.access_starts_at) is True
    assert subscription.is_active_at(subscription.access_ends_at) is False


@pytest.mark.parametrize(
    "status",
    [
        ProductSubscriptionStatus.INACTIVE,
        ProductSubscriptionStatus.CANCELLED,
        ProductSubscriptionStatus.EXPIRED,
    ],
)
def test_non_active_statuses_never_grant_pro_access(
    status: ProductSubscriptionStatus,
) -> None:
    assert _subscription(status=status).is_active_at(NOW) is False


def test_active_subscription_without_end_remains_effective_after_start() -> None:
    subscription = _subscription(ends=None)

    assert subscription.is_active_at(NOW + timedelta(days=365)) is True


def test_future_active_subscription_is_not_effective_yet() -> None:
    subscription = _subscription(
        starts=NOW + timedelta(hours=1),
        ends=NOW + timedelta(days=31),
    )

    assert subscription.is_active_at(NOW) is False


def test_contract_rejects_invalid_time_ranges_and_naive_datetimes() -> None:
    with pytest.raises(ValueError):
        _subscription(starts=NOW, ends=NOW)

    naive = datetime(2026, 9, 27, 12, 0)
    with pytest.raises(ValueError):
        _subscription(starts=naive)


def test_migration_is_provider_neutral_and_server_only() -> None:
    sql = _migration_text().casefold()

    assert "public.dexsato_product_subscriptions" in sql
    assert "references public.dexsato_product_users(id) on delete cascade" in sql
    assert "user_id uuid not null unique" in sql
    assert "plan_code in ('founder_pro', 'pro')" in sql
    assert "status in ('active', 'inactive', 'cancelled', 'expired')" in sql
    assert "enable row level security" in sql
    assert "revoke all on table public.dexsato_product_subscriptions from anon, authenticated" in sql
    assert "grant select, insert, update, delete on table public.dexsato_product_subscriptions to service_role" in sql

    for forbidden in (
        "stripe",
        "payment_provider",
        "payment_intent",
        "billing_webhook",
        "customer_id",
        "subscription_id text",
    ):
        assert forbidden not in sql


def test_migration_enforces_subscription_time_integrity() -> None:
    sql = _migration_text().casefold()

    assert "access_ends_at is null or access_ends_at > access_starts_at" in sql
    assert "updated_at >= created_at" in sql
