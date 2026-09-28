from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from application.product_entitlement_service import ProductEntitlementService
from application.product_identity_runtime import build_telegram_pro_alert_gate
from application.product_subscription_models import ProductSubscription, ProductSubscriptionPlan, ProductSubscriptionStatus
from application.telegram_pro_alert_gate import TelegramCustomerLink, TelegramProAlertGate


def _subscription(user_id, *, ended=False):
    now = datetime.now(UTC)
    return ProductSubscription(
        id=uuid4(), user_id=user_id, plan_code=ProductSubscriptionPlan.PRO,
        status=ProductSubscriptionStatus.ACTIVE,
        access_starts_at=now - timedelta(days=2),
        access_ends_at=now - timedelta(seconds=1) if ended else now + timedelta(days=1),
        created_at=now - timedelta(days=3), updated_at=now - timedelta(days=2),
    )


def test_only_linked_active_pro_reaches_customer_transport():
    user = uuid4()
    link = TelegramCustomerLink(user, 42, 42)
    class Links:
        def get_active_for_user(self, *, user_id): return link
    class Subscriptions:
        def get_for_user(self, *, user_id): return _subscription(user_id)
    sends = []
    gate = TelegramProAlertGate(Links(), ProductEntitlementService(Subscriptions()))
    assert gate.deliver(user_id=user, message="Signal", send=lambda **kw: sends.append(kw))
    assert sends == [{"chat_id": 42, "message": "Signal"}]


def test_public_expired_unlinked_malformed_and_storage_failure_never_send():
    user = uuid4()
    sends = []
    class Links:
        link = TelegramCustomerLink(user, 42, 42)
        def get_active_for_user(self, *, user_id): return self.link
    class Subscriptions:
        subscription = None
        def get_for_user(self, *, user_id):
            if self.subscription == "failure": raise RuntimeError("database down")
            return self.subscription
    links, subscriptions = Links(), Subscriptions()
    gate = TelegramProAlertGate(links, ProductEntitlementService(subscriptions))
    deliver = lambda: gate.deliver(user_id=user, message="Signal", send=lambda **kw: sends.append(kw))
    assert not deliver()
    subscriptions.subscription = _subscription(user, ended=True)
    assert not deliver()
    subscriptions.subscription = "failure"
    assert not deliver()
    subscriptions.subscription = _subscription(user)
    links.link = None
    assert not deliver()
    links.link = TelegramCustomerLink(uuid4(), 42, 42)
    assert not deliver()
    links.link = TelegramCustomerLink(user, 42, 43)
    assert not deliver()
    assert sends == []


def test_link_storage_failure_and_bad_message_fail_closed():
    user = uuid4()
    class Links:
        def get_active_for_user(self, *, user_id): raise RuntimeError("link store down")
    class Entitlements:
        def resolve(self, principal): raise AssertionError("must not be called")
    gate = TelegramProAlertGate(Links(), Entitlements())
    assert gate.recipient_for(user_id=user) is None
    assert not gate.deliver(user_id=user, message=" ", send=lambda **kw: None)


def test_builder_requires_enabled_auth_and_uses_server_secret_for_both_readers():
    calls = []
    class Client:
        def table(self, name): raise AssertionError("not used")
    def create_client(url, key):
        calls.append((url, key))
        return Client()
    with patch.dict("os.environ", {}, clear=True):
        try:
            build_telegram_pro_alert_gate(create_client=create_client)
        except RuntimeError as error:
            assert "disabled" in str(error)
        else:
            raise AssertionError("disabled runtime created a gate")
    assert calls == []
    with patch.dict("os.environ", {
        "DEXSATO_PRODUCT_AUTH_ENABLED": "true",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_public",
        "SUPABASE_SECRET_KEY": "sb_secret_server",
    }, clear=True):
        gate = build_telegram_pro_alert_gate(create_client=create_client)
    assert isinstance(gate, TelegramProAlertGate)
    assert calls == [("https://project.supabase.co", "sb_secret_server")] * 2