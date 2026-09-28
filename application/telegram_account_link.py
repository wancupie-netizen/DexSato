"""One-time, server-side binding of a product user to a private Telegram chat."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID


class TelegramLinkRepository(Protocol):
    def create_request(self, *, user_id: UUID, token_hash: str, created_at: datetime, expires_at: datetime) -> None: ...

    def redeem_request(self, *, token_hash: str, telegram_user_id: int, chat_id: int) -> bool: ...


class TelegramLinkService:
    def __init__(self, repository: TelegramLinkRepository) -> None:
        self._repository = repository

    def issue(self, *, user_id: UUID, now: datetime | None = None) -> str:
        if not isinstance(user_id, UUID):
            raise TypeError("user_id must be a UUID")
        instant = datetime.now(UTC) if now is None else now
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        instant = instant.astimezone(UTC)
        token = secrets.token_urlsafe(32)
        self._repository.create_request(
            user_id=user_id,
            token_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
            created_at=instant,
            expires_at=instant + timedelta(minutes=10),
        )
        return token

    def redeem(self, *, token: str, telegram_user_id: int, chat_id: int) -> bool:
        if not isinstance(token, str) or len(token) != 43 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in token):
            return False
        if isinstance(telegram_user_id, bool) or not isinstance(telegram_user_id, int) or telegram_user_id <= 0:
            return False
        if isinstance(chat_id, bool) or not isinstance(chat_id, int) or chat_id <= 0 or chat_id != telegram_user_id:
            return False
        return self._repository.redeem_request(
            token_hash=hashlib.sha256(token.encode("ascii")).hexdigest(),
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
        )
