"""Provider-neutral subscription persistence contract for DexSato."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID


class ProductSubscriptionPlan(str, Enum):
    FOUNDER_PRO = "founder_pro"
    PRO = "pro"


class ProductSubscriptionStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


def _utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ProductSubscription:
    id: UUID
    user_id: UUID
    plan_code: ProductSubscriptionPlan
    status: ProductSubscriptionStatus
    access_starts_at: datetime
    access_ends_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        starts = _utc(self.access_starts_at, field_name="access_starts_at")
        ends = (
            None
            if self.access_ends_at is None
            else _utc(self.access_ends_at, field_name="access_ends_at")
        )
        created = _utc(self.created_at, field_name="created_at")
        updated = _utc(self.updated_at, field_name="updated_at")

        if ends is not None and ends <= starts:
            raise ValueError("access_ends_at must be after access_starts_at")
        if updated < created:
            raise ValueError("updated_at must not be before created_at")

    def is_active_at(self, now: datetime) -> bool:
        """Return the effective server-side subscription state at a point in time."""

        instant = _utc(now, field_name="now")
        starts = self.access_starts_at.astimezone(UTC)
        ends = (
            None
            if self.access_ends_at is None
            else self.access_ends_at.astimezone(UTC)
        )
        return (
            self.status is ProductSubscriptionStatus.ACTIVE
            and instant >= starts
            and (ends is None or instant < ends)
        )
