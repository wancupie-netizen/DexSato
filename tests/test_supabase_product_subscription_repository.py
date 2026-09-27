from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from application.product_subscription_models import (
    ProductSubscriptionPlan,
    ProductSubscriptionStatus,
)
from application.supabase_product_subscription_repository import (
    ProductSubscriptionPersistenceError,
    SupabaseProductSubscriptionRepository,
)


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
USER_ID = UUID("11111111-1111-4111-8111-111111111111")
SUBSCRIPTION_ID = UUID("22222222-2222-4222-8222-222222222222")


def _row(
    *,
    status: str = "active",
    plan_code: str = "founder_pro",
    access_ends_at: str | None = None,
):
    return {
        "id": str(SUBSCRIPTION_ID),
        "user_id": str(USER_ID),
        "plan_code": plan_code,
        "status": status,
        "access_starts_at": (NOW - timedelta(days=1)).isoformat(),
        "access_ends_at": (
            (NOW + timedelta(days=30)).isoformat()
            if access_ends_at is None
            else access_ends_at
        ),
        "created_at": (NOW - timedelta(days=2)).isoformat(),
        "updated_at": (NOW - timedelta(hours=1)).isoformat(),
    }


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = None
        self.payload = None
        self.filters = []
        self.limit_value = None

    def select(self, fields):
        self.operation = "select"
        self.payload = fields
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        self.client.calls.append(
            (
                self.table,
                self.operation,
                self.payload,
                tuple(self.filters),
                self.limit_value,
            )
        )
        return SimpleNamespace(data=self.client.reply(self))


class FakeClient:
    def __init__(self, replies=None, *, error: Exception | None = None):
        self.replies = iter(replies or [])
        self.error = error
        self.calls = []

    def table(self, name):
        return Query(self, name)

    def reply(self, query):
        if self.error is not None:
            raise self.error
        return next(self.replies)


def test_get_for_user_uses_exact_server_subscription_table_and_filter() -> None:
    client = FakeClient([[_row()]])
    repository = SupabaseProductSubscriptionRepository(client)

    subscription = repository.get_for_user(user_id=USER_ID)

    assert subscription is not None
    assert subscription.id == SUBSCRIPTION_ID
    assert subscription.user_id == USER_ID
    assert subscription.plan_code is ProductSubscriptionPlan.FOUNDER_PRO
    assert subscription.status is ProductSubscriptionStatus.ACTIVE

    call = client.calls[0]
    assert call[0] == "dexsato_product_subscriptions"
    assert call[1] == "select"
    assert ("eq", "user_id", str(USER_ID)) in call[3]
    assert call[4] == 2


def test_missing_subscription_returns_none() -> None:
    repository = SupabaseProductSubscriptionRepository(FakeClient([[]]))

    assert repository.get_for_user(user_id=USER_ID) is None


def test_ambiguous_subscription_rows_fail_closed() -> None:
    repository = SupabaseProductSubscriptionRepository(
        FakeClient([[_row(), _row()]])
    )

    with pytest.raises(ProductSubscriptionPersistenceError):
        repository.get_for_user(user_id=USER_ID)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "unknown"),
        ("plan_code", "enterprise"),
    ],
)
def test_invalid_bounded_values_fail_closed(field: str, value: str) -> None:
    row = _row()
    row[field] = value
    repository = SupabaseProductSubscriptionRepository(FakeClient([[row]]))

    with pytest.raises(ProductSubscriptionPersistenceError):
        repository.get_for_user(user_id=USER_ID)


def test_invalid_subscription_time_window_fails_closed() -> None:
    row = _row(access_ends_at=(NOW - timedelta(days=2)).isoformat())
    repository = SupabaseProductSubscriptionRepository(FakeClient([[row]]))

    with pytest.raises(ProductSubscriptionPersistenceError):
        repository.get_for_user(user_id=USER_ID)


def test_client_failure_is_wrapped_as_persistence_error() -> None:
    repository = SupabaseProductSubscriptionRepository(
        FakeClient(error=RuntimeError("database unavailable"))
    )

    with pytest.raises(ProductSubscriptionPersistenceError):
        repository.get_for_user(user_id=USER_ID)


def test_user_id_must_be_uuid() -> None:
    repository = SupabaseProductSubscriptionRepository(FakeClient([[]]))

    with pytest.raises(TypeError):
        repository.get_for_user(user_id="not-a-uuid")
