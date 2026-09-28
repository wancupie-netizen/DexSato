from types import SimpleNamespace
from uuid import uuid4

import pytest

from application.supabase_telegram_pro_recipient import (
    SupabaseTelegramCustomerLinkReader, TelegramRecipientPersistenceError,
)


class Query:
    def __init__(self, rows): self.rows = rows
    def select(self, *args): return self
    def eq(self, *args): return self
    def limit(self, *args): return self
    def execute(self): return SimpleNamespace(data=self.rows)


class Client:
    def __init__(self, user_rows, link_rows):
        self.user_rows, self.link_rows = user_rows, link_rows
    def table(self, name):
        return Query(self.user_rows if name == "dexsato_product_users" else self.link_rows)


def test_reader_checks_active_product_user_and_linked_private_chat():
    user = uuid4()
    link = {"user_id": str(user), "telegram_user_id": 41, "chat_id": 41}
    reader = SupabaseTelegramCustomerLinkReader(Client([{"id": str(user), "disabled_at": None}], [link]))
    assert reader.get_active_for_user(user_id=user).chat_id == 41
    reader = SupabaseTelegramCustomerLinkReader(Client([{"id": str(user), "disabled_at": "2026-09-28T00:00:00Z"}], [link]))
    assert reader.get_active_for_user(user_id=user) is None


def test_reader_rejects_ambiguous_or_malformed_link_data():
    user = uuid4()
    valid_user = [{"id": str(user), "disabled_at": None}]
    with pytest.raises(TelegramRecipientPersistenceError):
        SupabaseTelegramCustomerLinkReader(Client(valid_user, [
            {"user_id": str(user), "telegram_user_id": 41, "chat_id": 41},
            {"user_id": str(user), "telegram_user_id": 42, "chat_id": 42},
        ])).get_active_for_user(user_id=user)
    with pytest.raises(TelegramRecipientPersistenceError):
        SupabaseTelegramCustomerLinkReader(Client(valid_user, [
            {"user_id": str(user), "telegram_user_id": "41", "chat_id": 41},
        ])).get_active_for_user(user_id=user)