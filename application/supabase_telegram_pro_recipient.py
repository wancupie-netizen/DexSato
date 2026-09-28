"""Read linked customer identity through a server-only Supabase client."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from application.telegram_pro_alert_gate import TelegramCustomerLink


class TelegramRecipientPersistenceError(RuntimeError):
    pass


def _one(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None)
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data) or len(data) > 1:
        raise TelegramRecipientPersistenceError("Invalid linked customer response.")
    return data[0] if data else None


class SupabaseTelegramCustomerLinkReader:
    def __init__(self, client: Any) -> None:
        if client is None or not callable(getattr(client, "table", None)):
            raise TypeError("a server-side Supabase client is required")
        self._client = client

    def get_active_for_user(self, *, user_id: UUID) -> TelegramCustomerLink | None:
        if not isinstance(user_id, UUID):
            raise TypeError("user_id must be a UUID")
        try:
            user = _one(self._client.table("dexsato_product_users")
                .select("id,disabled_at").eq("id", str(user_id)).limit(2).execute())
            if (user is None or str(user.get("id")) != str(user_id)
                    or "disabled_at" not in user or user["disabled_at"] is not None):
                return None
            row = _one(self._client.table("dexsato_telegram_account_links")
                .select("user_id,telegram_user_id,chat_id").eq("user_id", str(user_id))
                .limit(2).execute())
            if row is None:
                return None
            if type(row.get("telegram_user_id")) is not int or type(row.get("chat_id")) is not int:
                raise TelegramRecipientPersistenceError("Invalid linked customer identity.")
            return TelegramCustomerLink(
                user_id=UUID(str(row["user_id"])),
                telegram_user_id=row["telegram_user_id"],
                chat_id=row["chat_id"],
            )
        except TelegramRecipientPersistenceError:
            raise
        except Exception as error:
            raise TelegramRecipientPersistenceError("Unable to resolve Telegram customer.") from error