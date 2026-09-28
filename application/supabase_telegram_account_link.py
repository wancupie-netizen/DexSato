"""Server-only persistence for Telegram account linking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID


class TelegramLinkPersistenceError(RuntimeError):
    pass


class SupabaseTelegramLinkRepository:
    def __init__(self, client: Any) -> None:
        if client is None or not callable(getattr(client, "table", None)) or not callable(getattr(client, "rpc", None)):
            raise TypeError("a server-side Supabase client is required")
        self._client = client

    def create_request(self, *, user_id: UUID, token_hash: str, created_at: datetime, expires_at: datetime) -> None:
        try:
            result = self._client.table("dexsato_telegram_link_requests").insert({
                "user_id": str(user_id),
                "token_hash": token_hash,
                "created_at": created_at.astimezone(UTC).isoformat(),
                "expires_at": expires_at.astimezone(UTC).isoformat(),
            }).execute()
            if not isinstance(getattr(result, "data", None), list) or len(result.data) != 1:
                raise TelegramLinkPersistenceError("Link request was not persisted.")
        except Exception as error:
            raise TelegramLinkPersistenceError("Unable to create Telegram link request.") from error

    def redeem_request(self, *, token_hash: str, telegram_user_id: int, chat_id: int) -> bool:
        try:
            result = self._client.rpc("dexsato_redeem_telegram_link", {
                "p_token_hash": token_hash,
                "p_telegram_user_id": telegram_user_id,
                "p_chat_id": chat_id,
            }).execute()
            if type(getattr(result, "data", None)) is not bool:
                raise TelegramLinkPersistenceError("Invalid Telegram link response.")
            return result.data
        except Exception as error:
            raise TelegramLinkPersistenceError("Unable to redeem Telegram link request.") from error
