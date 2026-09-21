"""Provider-neutral product-session lifecycle and token handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import re
import secrets
from uuid import uuid4

from application.product_identity_models import (
    IssuedProductSession,
    ProductPrincipal,
    ProductSession,
)
from application.product_identity_repository import ProductIdentityRepository


_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MINIMUM_TTL_SECONDS = 300
_MAXIMUM_TTL_SECONDS = 90 * 24 * 60 * 60
_DEFAULT_TOUCH_INTERVAL_SECONDS = 300


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) > 254 or not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("invalid email")
    return normalized


def mask_email(value: str) -> str:
    normalized = normalize_email(value)
    local, domain = normalized.split("@", 1)
    return f"{local[0]}***@{domain}"


def hash_session_token(token: str) -> str:
    if not isinstance(token, str) or not token:
        raise ValueError("session token is required")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class ProductIdentityService:
    def __init__(
        self,
        repository: ProductIdentityRepository,
        *,
        session_ttl_seconds: int = 30 * 24 * 60 * 60,
        touch_interval_seconds: int = _DEFAULT_TOUCH_INTERVAL_SECONDS,
    ) -> None:
        if not _MINIMUM_TTL_SECONDS <= session_ttl_seconds <= _MAXIMUM_TTL_SECONDS:
            raise ValueError("session TTL is outside the allowed boundary")
        if touch_interval_seconds < 0:
            raise ValueError("touch interval cannot be negative")
        self._repository = repository
        self._session_ttl = timedelta(seconds=session_ttl_seconds)
        self._touch_interval = timedelta(seconds=touch_interval_seconds)

    def create_authenticated_session(
        self,
        *,
        auth_provider: str,
        auth_subject: str,
        email: str,
        now: datetime | None = None,
    ) -> IssuedProductSession:
        provider = auth_provider.strip().casefold()
        subject = auth_subject.strip()
        if not provider or len(provider) > 64:
            raise ValueError("invalid auth provider")
        if not subject or len(subject) > 255:
            raise ValueError("invalid auth subject")

        observed_at = _require_utc(now or _utc_now())
        email_normalized = normalize_email(email)
        user = self._repository.upsert_user(
            auth_provider=provider,
            auth_subject=subject,
            email_normalized=email_normalized,
            now=observed_at,
        )

        raw_token = secrets.token_urlsafe(32)
        expires_at = observed_at + self._session_ttl
        session = ProductSession(
            id=uuid4(),
            user_id=user.id,
            token_hash=hash_session_token(raw_token),
            created_at=observed_at,
            expires_at=expires_at,
            last_seen_at=observed_at,
        )
        self._repository.create_session(session)
        return IssuedProductSession(
            token=raw_token,
            principal=ProductPrincipal(
                authenticated=True,
                user_id=user.id,
                email_masked=mask_email(user.email_normalized),
            ),
            expires_at=expires_at,
        )

    def authenticate(
        self,
        token: str | None,
        *,
        now: datetime | None = None,
    ) -> ProductPrincipal:
        if not token:
            return ProductPrincipal.guest()

        observed_at = _require_utc(now or _utc_now())
        resolved = self._repository.resolve_session(token_hash=hash_session_token(token))
        if resolved is None:
            return ProductPrincipal.guest()
        if resolved.session.revoked_at is not None:
            return ProductPrincipal.guest()
        if resolved.session.expires_at <= observed_at:
            return ProductPrincipal.guest()
        if resolved.user.disabled_at is not None:
            return ProductPrincipal.guest()

        if observed_at - resolved.session.last_seen_at >= self._touch_interval:
            self._repository.touch_session(
                session_id=resolved.session.id,
                last_seen_at=observed_at,
            )

        return ProductPrincipal(
            authenticated=True,
            user_id=resolved.user.id,
            email_masked=mask_email(resolved.user.email_normalized),
        )

    def logout(self, token: str | None, *, now: datetime | None = None) -> bool:
        if not token:
            return False
        revoked_at = _require_utc(now or _utc_now())
        return self._repository.revoke_session(
            token_hash=hash_session_token(token),
            revoked_at=revoked_at,
        )
