from uuid import uuid4

import pytest

from application.product_entitlement_policy import PRO_ENTITLEMENTS, PUBLIC_ENTITLEMENTS
from application.telegram_customer_alert import send_customer_telegram_alert
from application.telegram_pro_alert_gate import TelegramCustomerLink, TelegramProAlertGate


class Response:
    def raise_for_status(self):
        pass


def test_pro_customer_transport_uses_linked_chat_not_founder_default(monkeypatch):
    user = uuid4()
    class Links:
        def get_active_for_user(self, *, user_id):
            return TelegramCustomerLink(user, 902, 902)
    class Entitlements:
        def resolve(self, principal):
            return PRO_ENTITLEMENTS
    calls = []
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
    gate = TelegramProAlertGate(Links(), Entitlements())
    assert send_customer_telegram_alert(
        gate=gate, user_id=user, message="Signal", bot_token="test-token",
        post=lambda *args, **kwargs: (calls.append((args, kwargs)) or Response()),
    )
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("https://api.telegram.org/bottest-token/sendMessage",)
    assert kwargs["json"]["chat_id"] == "902"
    assert kwargs["json"]["text"] == "Signal"
    assert kwargs["timeout"] == 15


def test_denied_customer_never_calls_transport():
    user = uuid4()
    class Links:
        def get_active_for_user(self, *, user_id):
            return TelegramCustomerLink(user, 902, 902)
    class Entitlements:
        def resolve(self, principal):
            return PUBLIC_ENTITLEMENTS
    gate = TelegramProAlertGate(Links(), Entitlements())
    def forbidden_post(*args, **kwargs):
        raise AssertionError("customer network request was made")
    assert not send_customer_telegram_alert(
        gate=gate, user_id=user, message="Signal", bot_token="test-token", post=forbidden_post,
    )


def test_transport_error_is_reported_to_caller():
    user = uuid4()
    class Links:
        def get_active_for_user(self, *, user_id):
            return TelegramCustomerLink(user, 902, 902)
    class Entitlements:
        def resolve(self, principal):
            return PRO_ENTITLEMENTS
    gate = TelegramProAlertGate(Links(), Entitlements())
    def failed_post(*args, **kwargs):
        raise RuntimeError("network unavailable")
    with pytest.raises(RuntimeError, match="network unavailable"):
        send_customer_telegram_alert(
            gate=gate, user_id=user, message="Signal", bot_token="test-token", post=failed_post,
        )