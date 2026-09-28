from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from application import telegram_customer_dispatch as dispatch


def test_disabled_default_makes_no_database_or_network_calls(monkeypatch):
    monkeypatch.delenv("DEXSATO_CUSTOMER_TELEGRAM_ALERTS_ENABLED", raising=False)
    assert dispatch.deliver_customer_changes(
        changes=[{"new_decision": "ALERT"}]
    ) == {"status": "DISABLED", "sent": 0, "failed": 0}


def test_only_alert_changes_are_formatted_for_customers():
    assert dispatch.customer_change_message(
        [{"new_decision": "WATCH"}]
    ) == ""
    message = dispatch.customer_change_message(
        [{"new_decision": "ALERT", "token": "SOL"}]
    )
    assert "SOL" in message and "ALERT" in message
    assert "Founder action" not in message
    assert "Not a trade signal" in message


def test_linked_customer_ids_paginates_in_order_and_rejects_bad_page():
    users = sorted([str(uuid4()) for _ in range(3)])

    class Query:
        previous = None
        size = None

        def select(self, columns):
            return self

        def gt(self, column, value):
            self.previous = value
            return self

        def order(self, column):
            return self

        def limit(self, size):
            self.size = size
            return self

        def execute(self):
            remaining = [
                user for user in users
                if self.previous is None or user > self.previous
            ]
            return SimpleNamespace(
                data=[{"user_id": user} for user in remaining[:self.size]]
            )

    class Client:
        def table(self, table):
            assert table == "dexsato_telegram_account_links"
            return Query()

    assert [
        str(user)
        for user in dispatch.linked_customer_ids(Client(), page_size=2)
    ] == users

    class Broken:
        def table(self, table):
            return self

        def select(self, columns):
            return self

        def order(self, column):
            return self

        def limit(self, size):
            return self

        def execute(self):
            return SimpleNamespace(data=[{"user_id": "invalid"}])

    with pytest.raises(RuntimeError, match="identity"):
        dispatch.linked_customer_ids(Broken())


def test_enabled_fanout_rechecks_each_user_and_keeps_failures_separate(monkeypatch):
    user1, user2 = uuid4(), uuid4()
    monkeypatch.setenv("DEXSATO_CUSTOMER_TELEGRAM_ALERTS_ENABLED", "true")
    config = SimpleNamespace(
        enabled=True,
        supabase_url="https://example.supabase.co",
        secret_key="server",
    )
    calls = []

    def send_alert(*, gate, user_id, message):
        calls.append(user_id)
        if user_id == user2:
            raise RuntimeError("Telegram unavailable")
        return True

    with patch.object(
        dispatch, "product_identity_runtime_config", return_value=config
    ), patch.object(
        dispatch, "_default_create_client", return_value=object()
    ) as client, patch.object(
        dispatch, "linked_customer_ids", return_value=[user1, user2]
    ), patch.object(
        dispatch, "build_telegram_pro_alert_gate", return_value=object()
    ), patch.object(
        dispatch, "send_customer_telegram_alert", side_effect=send_alert
    ):
        result = dispatch.deliver_customer_changes(
            changes=[{"new_decision": "ALERT", "token": "SOL"}]
        )

    assert result == {"status": "FAILED", "sent": 1, "failed": 1}
    assert calls == [user1, user2]
    client.assert_called_once_with(config.supabase_url, config.secret_key)


def test_customer_delivery_failure_does_not_change_founder_run_status():
    from founder_scheduler import execute_founder_scheduler

    def failed_customers(*, changes):
        raise RuntimeError("customer DB unavailable")

    result = execute_founder_scheduler(
        load_snapshot=lambda: {"generated_at": "now", "total_coins": 0},
        generate_snapshot=lambda: {"snapshot_file": "example.json"},
        detect_changes=lambda **kwargs: [
            {
                "token": "SOL",
                "old_decision": "WATCH",
                "new_decision": "ALERT",
            }
        ],
        send_digest=lambda **kwargs: {"sent": True},
        deliver_customers=failed_customers,
    )
    assert result["automation_status"] == "HEALTHY"
    assert result["telegram_status"] == "SENT"
    assert result["customer_telegram_status"] == "FAILED"
