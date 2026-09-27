"""Read-only Supabase repository for provider-neutral product subscriptions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from application.product_subscription_models import (
    ProductSubscription,
    ProductSubscriptionPlan,
    ProductSubscriptionStatus,
)


_TABLE = "dexsato_product_subscriptions"
_FIELDS = (
    "id,user_id,plan_code,status,access_starts_at,access_ends_at,created_at,updated_at"
)


class ProductSubscriptionPersistenceError(RuntimeError):
    """Raised when subscription persistence cannot be resolved safely."""


def _datetime(value: Any, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ProductSubscriptionPersistenceError("Invalid subscription timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProductSubscriptionPersistenceError(
            "Invalid subscription timestamp."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProductSubscriptionPersistenceError("Invalid subscription timestamp.")
    return parsed.astimezone(UTC)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ProductSubscriptionPersistenceError(
            "Invalid Supabase subscription response."
        )
    return data


def _one(response: Any) -> dict[str, Any] | None:
    rows = _rows(response)
    if not rows:
        return None
    if len(rows) != 1:
        raise ProductSubscriptionPersistenceError(
            "Subscription query returned an ambiguous result."
        )
    return rows[0]


def _subscription(row: dict[str, Any]) -> ProductSubscription:
    try:
        return ProductSubscription(
            id=UUID(str(row["id"])),
            user_id=UUID(str(row["user_id"])),
            plan_code=ProductSubscriptionPlan(str(row["plan_code"])),
            status=ProductSubscriptionStatus(str(row["status"])),
            access_starts_at=_datetime(row["access_starts_at"]),
            access_ends_at=_datetime(row.get("access_ends_at"), nullable=True),
            created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
        )
    except ProductSubscriptionPersistenceError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise ProductSubscriptionPersistenceError(
            "Invalid product subscription row."
        ) from error


class SupabaseProductSubscriptionRepository:
    """Server-side subscription reader. No browser-facing write surface is exposed."""

    def __init__(self, client: Any) -> None:
        if client is None or not callable(getattr(client, "table", None)):
            raise TypeError("a Supabase repository client is required")
        self._client = client

    def get_for_user(self, *, user_id: UUID) -> ProductSubscription | None:
        if not isinstance(user_id, UUID):
            raise TypeError("user_id must be a UUID")
        try:
            response = (
                self._client.table(_TABLE)
                .select(_FIELDS)
                .eq("user_id", str(user_id))
                .limit(2)
                .execute()
            )
            row = _one(response)
            return None if row is None else _subscription(row)
        except ProductSubscriptionPersistenceError:
            raise
        except Exception as error:
            raise ProductSubscriptionPersistenceError(
                "Unable to resolve product subscription."
            ) from error
