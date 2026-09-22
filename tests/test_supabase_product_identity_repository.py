from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from application.product_identity_models import ProductSession
from application.supabase_product_identity_repository import (
    SupabaseProductIdentityRepository,
)


NOW = datetime(2026, 9, 22, tzinfo=UTC)
USER_ID = UUID("11111111-1111-4111-8111-111111111111")


def _user_row():
    return {
        "id": str(USER_ID),
        "auth_provider": "supabase",
        "auth_subject": "provider-user-1",
        "email_normalized": "user@example.com",
        "created_at": NOW.isoformat(),
        "last_login_at": NOW.isoformat(),
        "disabled_at": None,
    }


class Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = None
        self.payload = None
        self.filters = []

    def select(self, fields): self.operation = "select"; self.payload = fields; return self
    def insert(self, payload): self.operation = "insert"; self.payload = payload; return self
    def update(self, payload): self.operation = "update"; self.payload = payload; return self
    def eq(self, field, value): self.filters.append(("eq", field, value)); return self
    def is_(self, field, value): self.filters.append(("is", field, value)); return self
    def limit(self, value): return self
    def execute(self):
        self.client.calls.append((self.table, self.operation, self.payload, tuple(self.filters)))
        return SimpleNamespace(data=self.client.reply(self))


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def table(self, name): return Query(self, name)
    def reply(self, query): return next(self.replies)


def test_existing_user_is_updated_without_replacing_primary_key():
    client = FakeClient([[_user_row()], [_user_row()]])
    repository = SupabaseProductIdentityRepository(client)

    user = repository.upsert_user(
        auth_provider="supabase",
        auth_subject="provider-user-1",
        email_normalized="user@example.com",
        now=NOW,
    )

    assert user.id == USER_ID
    update = client.calls[1]
    assert update[1] == "update"
    assert "id" not in update[2]
    assert ("eq", "id", str(USER_ID)) in update[3]


def test_session_round_trip_uses_hash_only_and_exact_contract_tables():
    session_id = uuid4()
    token_hash = "a" * 64
    session_row = {
        "id": str(session_id),
        "user_id": str(USER_ID),
        "token_hash": token_hash,
        "created_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(days=30)).isoformat(),
        "last_seen_at": NOW.isoformat(),
        "revoked_at": None,
    }
    client = FakeClient([[session_row], [session_row], [_user_row()]])
    repository = SupabaseProductIdentityRepository(client)
    session = ProductSession(
        id=session_id,
        user_id=USER_ID,
        token_hash=token_hash,
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
        last_seen_at=NOW,
    )

    repository.create_session(session)
    resolved = repository.resolve_session(token_hash=token_hash)

    assert client.calls[0][0] == "dexsato_product_sessions"
    assert client.calls[0][2]["token_hash"] == token_hash
    assert "token" not in client.calls[0][2]
    assert resolved.session.id == session_id
    assert resolved.user.id == USER_ID


def test_touch_and_revoke_are_narrowly_filtered():
    session_id = uuid4()
    client = FakeClient([[{"id": str(session_id)}], [{"id": str(session_id)}]])
    repository = SupabaseProductIdentityRepository(client)

    repository.touch_session(session_id=session_id, last_seen_at=NOW)
    assert repository.revoke_session(token_hash="b" * 64, revoked_at=NOW) is True

    assert ("eq", "id", str(session_id)) in client.calls[0][3]
    assert ("eq", "token_hash", "b" * 64) in client.calls[1][3]
    assert ("is", "revoked_at", "null") in client.calls[1][3]
