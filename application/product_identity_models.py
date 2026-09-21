"""Product identity value objects with no web or provider dependency."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ProductUser:
    id: UUID
    auth_provider: str
    auth_subject: str
    email_normalized: str
    created_at: datetime
    last_login_at: datetime
    disabled_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProductSession:
    id: UUID
    user_id: UUID
    token_hash: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResolvedProductSession:
    user: ProductUser
    session: ProductSession


@dataclass(frozen=True, slots=True)
class ProductPrincipal:
    authenticated: bool
    user_id: UUID | None = None
    email_masked: str | None = None

    @classmethod
    def guest(cls) -> "ProductPrincipal":
        return cls(authenticated=False)


@dataclass(frozen=True, slots=True)
class IssuedProductSession:
    token: str = field(repr=False)
    principal: ProductPrincipal
    expires_at: datetime
