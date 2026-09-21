from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from application.product_identity_models import (
    ProductSession,
    ProductUser,
    ResolvedProductSession,
)
from application.product_identity_service import (
    ProductIdentityService,
    hash_session_token,
    mask_email,
    normalize_email,
)


NOW = datetime(2026, 9, 21, 17, 0, tzinfo=UTC)


class FakeProductIdentityRepository:
    def __init__(self) -> None:
        self.users_by_identity: dict[tuple[str, str], ProductUser] = {}
        self.users_by_id: dict[UUID, ProductUser] = {}
        self.sessions_by_hash: dict[str, ProductSession] = {}
        self.touches: list[tuple[UUID, datetime]] = []

    def upsert_user(
        self,
        *,
        auth_provider: str,
        auth_subject: str,
        email_normalized: str,
        now: datetime,
    ) -> ProductUser:
        key = (auth_provider, auth_subject)
        current = self.users_by_identity.get(key)
        if current is None:
            current = ProductUser(
                id=uuid4(),
                auth_provider=auth_provider,
                auth_subject=auth_subject,
                email_normalized=email_normalized,
                created_at=now,
                last_login_at=now,
            )
        else:
            current = replace(
                current,
                email_normalized=email_normalized,
                last_login_at=now,
            )
        self.users_by_identity[key] = current
        self.users_by_id[current.id] = current
        return current

    def create_session(self, session: ProductSession) -> None:
        self.sessions_by_hash[session.token_hash] = session

    def resolve_session(self, *, token_hash: str) -> ResolvedProductSession | None:
        session = self.sessions_by_hash.get(token_hash)
        if session is None:
            return None
        return ResolvedProductSession(
            user=self.users_by_id[session.user_id],
            session=session,
        )

    def touch_session(self, *, session_id: UUID, last_seen_at: datetime) -> None:
        self.touches.append((session_id, last_seen_at))
        for token_hash, session in self.sessions_by_hash.items():
            if session.id == session_id:
                self.sessions_by_hash[token_hash] = replace(
                    session,
                    last_seen_at=last_seen_at,
                )
                return

    def revoke_session(self, *, token_hash: str, revoked_at: datetime) -> bool:
        session = self.sessions_by_hash.get(token_hash)
        if session is None or session.revoked_at is not None:
            return False
        self.sessions_by_hash[token_hash] = replace(session, revoked_at=revoked_at)
        return True

    def disable_user(self, user_id: UUID, *, at: datetime) -> None:
        user = replace(self.users_by_id[user_id], disabled_at=at)
        self.users_by_id[user_id] = user
        self.users_by_identity[(user.auth_provider, user.auth_subject)] = user


def test_creates_opaque_hashed_session_and_masked_principal() -> None:
    repository = FakeProductIdentityRepository()
    service = ProductIdentityService(repository)

    issued = service.create_authenticated_session(
        auth_provider=" Supabase ",
        auth_subject="auth-user-1",
        email=" User@Example.COM ",
        now=NOW,
    )

    assert issued.principal.authenticated is True
    assert issued.principal.email_masked == "u***@example.com"
    assert len(issued.token) >= 43
    stored = repository.sessions_by_hash[hash_session_token(issued.token)]
    assert stored.token_hash != issued.token
    assert issued.token not in repr(issued)
    assert stored.expires_at == NOW + timedelta(days=30)


def test_authenticates_active_session_and_throttles_touch_write() -> None:
    repository = FakeProductIdentityRepository()
    service = ProductIdentityService(repository, touch_interval_seconds=300)
    issued = service.create_authenticated_session(
        auth_provider="supabase",
        auth_subject="auth-user-2",
        email="two@example.com",
        now=NOW,
    )

    first = service.authenticate(issued.token, now=NOW + timedelta(seconds=299))
    second = service.authenticate(issued.token, now=NOW + timedelta(seconds=300))

    assert first.authenticated is True
    assert second.user_id == issued.principal.user_id
    assert len(repository.touches) == 1


def test_expired_revoked_and_disabled_sessions_fail_to_guest() -> None:
    repository = FakeProductIdentityRepository()
    service = ProductIdentityService(repository, session_ttl_seconds=300)
    issued = service.create_authenticated_session(
        auth_provider="supabase",
        auth_subject="auth-user-3",
        email="three@example.com",
        now=NOW,
    )

    assert service.authenticate(issued.token, now=NOW + timedelta(seconds=300)).authenticated is False

    active = service.create_authenticated_session(
        auth_provider="supabase",
        auth_subject="auth-user-4",
        email="four@example.com",
        now=NOW,
    )
    assert service.logout(active.token, now=NOW + timedelta(seconds=1)) is True
    assert service.authenticate(active.token, now=NOW + timedelta(seconds=2)).authenticated is False

    disabled = service.create_authenticated_session(
        auth_provider="supabase",
        auth_subject="auth-user-5",
        email="five@example.com",
        now=NOW,
    )
    repository.disable_user(disabled.principal.user_id, at=NOW + timedelta(seconds=1))
    assert service.authenticate(disabled.token, now=NOW + timedelta(seconds=2)).authenticated is False


def test_repeated_provider_identity_reuses_user_but_rotates_session() -> None:
    repository = FakeProductIdentityRepository()
    service = ProductIdentityService(repository)

    first = service.create_authenticated_session(
        auth_provider="supabase",
        auth_subject="stable-subject",
        email="first@example.com",
        now=NOW,
    )
    second = service.create_authenticated_session(
        auth_provider="supabase",
        auth_subject="stable-subject",
        email="updated@example.com",
        now=NOW + timedelta(minutes=1),
    )

    assert first.principal.user_id == second.principal.user_id
    assert first.token != second.token
    assert len(repository.sessions_by_hash) == 2


def test_invalid_inputs_and_ttl_fail_closed() -> None:
    repository = FakeProductIdentityRepository()
    with pytest.raises(ValueError):
        ProductIdentityService(repository, session_ttl_seconds=299)
    with pytest.raises(ValueError):
        ProductIdentityService(repository, session_ttl_seconds=90 * 24 * 60 * 60 + 1)
    with pytest.raises(ValueError):
        normalize_email("not-an-email")
    with pytest.raises(ValueError):
        hash_session_token("")
    with pytest.raises(ValueError):
        ProductIdentityService(repository).create_authenticated_session(
            auth_provider="supabase",
            auth_subject="subject",
            email="user@example.com",
            now=datetime(2026, 9, 21, 17, 0),
        )


def test_email_normalization_and_masking_are_deterministic() -> None:
    assert normalize_email("  USER+tag@Example.COM ") == "user+tag@example.com"
    assert mask_email("a@example.com") == "a***@example.com"
