"""Persistence contract for product users and opaque product sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.product_identity_models import (
    ProductSession,
    ProductUser,
    ResolvedProductSession,
)


class ProductIdentityRepository(Protocol):
    def upsert_user(
        self,
        *,
        auth_provider: str,
        auth_subject: str,
        email_normalized: str,
        now: datetime,
    ) -> ProductUser: ...

    def create_session(self, session: ProductSession) -> None: ...

    def resolve_session(self, *, token_hash: str) -> ResolvedProductSession | None: ...

    def touch_session(self, *, session_id: UUID, last_seen_at: datetime) -> None: ...

    def revoke_session(self, *, token_hash: str, revoked_at: datetime) -> bool: ...
