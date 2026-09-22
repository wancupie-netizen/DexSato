"""Supabase persistence adapter for product users and opaque sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from application.product_identity_models import (
    ProductSession,
    ProductUser,
    ResolvedProductSession,
)


_USERS_TABLE = "dexsato_product_users"
_SESSIONS_TABLE = "dexsato_product_sessions"
_USER_FIELDS = "id,auth_provider,auth_subject,email_normalized,created_at,last_login_at,disabled_at"
_SESSION_FIELDS = "id,user_id,token_hash,created_at,expires_at,last_seen_at,revoked_at"


class ProductIdentityPersistenceError(RuntimeError):
    """Raised when identity persistence fails closed."""


def _iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _datetime(value: Any, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ProductIdentityPersistenceError("Invalid identity timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProductIdentityPersistenceError("Invalid identity timestamp.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProductIdentityPersistenceError("Invalid identity timestamp.")
    return parsed.astimezone(UTC)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ProductIdentityPersistenceError("Invalid Supabase identity response.")
    return data


def _one(response: Any, *, required: bool) -> dict[str, Any] | None:
    rows = _rows(response)
    if not rows:
        if required:
            raise ProductIdentityPersistenceError("Expected identity row was not returned.")
        return None
    if len(rows) != 1:
        raise ProductIdentityPersistenceError("Identity query returned an ambiguous result.")
    return rows[0]


def _product_user(row: dict[str, Any]) -> ProductUser:
    try:
        return ProductUser(
            id=UUID(str(row["id"])),
            auth_provider=str(row["auth_provider"]),
            auth_subject=str(row["auth_subject"]),
            email_normalized=str(row["email_normalized"]),
            created_at=_datetime(row["created_at"]),
            last_login_at=_datetime(row["last_login_at"]),
            disabled_at=_datetime(row.get("disabled_at"), nullable=True),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ProductIdentityPersistenceError("Invalid product user row.") from error


def _product_session(row: dict[str, Any]) -> ProductSession:
    try:
        return ProductSession(
            id=UUID(str(row["id"])),
            user_id=UUID(str(row["user_id"])),
            token_hash=str(row["token_hash"]),
            created_at=_datetime(row["created_at"]),
            expires_at=_datetime(row["expires_at"]),
            last_seen_at=_datetime(row["last_seen_at"]),
            revoked_at=_datetime(row.get("revoked_at"), nullable=True),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ProductIdentityPersistenceError("Invalid product session row.") from error


class SupabaseProductIdentityRepository:
    def __init__(self, client: Any) -> None:
        if client is None or not callable(getattr(client, "table", None)):
            raise TypeError("a Supabase repository client is required")
        self._client = client

    def _find_user(self, *, auth_provider: str, auth_subject: str) -> dict[str, Any] | None:
        response = (
            self._client.table(_USERS_TABLE)
            .select(_USER_FIELDS)
            .eq("auth_provider", auth_provider)
            .eq("auth_subject", auth_subject)
            .limit(1)
            .execute()
        )
        return _one(response, required=False)

    def upsert_user(
        self,
        *,
        auth_provider: str,
        auth_subject: str,
        email_normalized: str,
        now: datetime,
    ) -> ProductUser:
        timestamp = _iso(now)
        try:
            existing = self._find_user(
                auth_provider=auth_provider,
                auth_subject=auth_subject,
            )
            if existing is None:
                try:
                    response = (
                        self._client.table(_USERS_TABLE)
                        .insert(
                            {
                                "id": str(uuid4()),
                                "auth_provider": auth_provider,
                                "auth_subject": auth_subject,
                                "email_normalized": email_normalized,
                                "created_at": timestamp,
                                "last_login_at": timestamp,
                                "disabled_at": None,
                            }
                        )
                        .execute()
                    )
                    return _product_user(_one(response, required=True))
                except Exception:
                    existing = self._find_user(
                        auth_provider=auth_provider,
                        auth_subject=auth_subject,
                    )
                    if existing is None:
                        raise

            response = (
                self._client.table(_USERS_TABLE)
                .update(
                    {
                        "email_normalized": email_normalized,
                        "last_login_at": timestamp,
                    }
                )
                .eq("id", str(existing["id"]))
                .execute()
            )
            return _product_user(_one(response, required=True))
        except ProductIdentityPersistenceError:
            raise
        except Exception as error:
            raise ProductIdentityPersistenceError("Unable to persist product user.") from error

    def create_session(self, session: ProductSession) -> None:
        try:
            response = (
                self._client.table(_SESSIONS_TABLE)
                .insert(
                    {
                        "id": str(session.id),
                        "user_id": str(session.user_id),
                        "token_hash": session.token_hash,
                        "created_at": _iso(session.created_at),
                        "expires_at": _iso(session.expires_at),
                        "last_seen_at": _iso(session.last_seen_at),
                        "revoked_at": None,
                    }
                )
                .execute()
            )
            _one(response, required=True)
        except ProductIdentityPersistenceError:
            raise
        except Exception as error:
            raise ProductIdentityPersistenceError("Unable to persist product session.") from error

    def resolve_session(self, *, token_hash: str) -> ResolvedProductSession | None:
        try:
            session_row = _one(
                self._client.table(_SESSIONS_TABLE)
                .select(_SESSION_FIELDS)
                .eq("token_hash", token_hash)
                .limit(1)
                .execute(),
                required=False,
            )
            if session_row is None:
                return None
            user_row = _one(
                self._client.table(_USERS_TABLE)
                .select(_USER_FIELDS)
                .eq("id", str(session_row["user_id"]))
                .limit(1)
                .execute(),
                required=True,
            )
            return ResolvedProductSession(
                user=_product_user(user_row),
                session=_product_session(session_row),
            )
        except ProductIdentityPersistenceError:
            raise
        except Exception as error:
            raise ProductIdentityPersistenceError("Unable to resolve product session.") from error

    def touch_session(self, *, session_id: UUID, last_seen_at: datetime) -> None:
        try:
            response = (
                self._client.table(_SESSIONS_TABLE)
                .update({"last_seen_at": _iso(last_seen_at)})
                .eq("id", str(session_id))
                .execute()
            )
            _one(response, required=True)
        except ProductIdentityPersistenceError:
            raise
        except Exception as error:
            raise ProductIdentityPersistenceError("Unable to touch product session.") from error

    def revoke_session(self, *, token_hash: str, revoked_at: datetime) -> bool:
        try:
            response = (
                self._client.table(_SESSIONS_TABLE)
                .update({"revoked_at": _iso(revoked_at)})
                .eq("token_hash", token_hash)
                .is_("revoked_at", "null")
                .execute()
            )
            return bool(_rows(response))
        except ProductIdentityPersistenceError:
            raise
        except Exception as error:
            raise ProductIdentityPersistenceError("Unable to revoke product session.") from error
