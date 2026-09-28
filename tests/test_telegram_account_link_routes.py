"""Request boundaries for Telegram identity linking."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.product_identity_models import ProductPrincipal
from application.telegram_account_link_routes import router


def _client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


_CONFIG = {
    "DEXSATO_TELEGRAM_LINK_ENABLED": "true",
    "DEXSATO_TELEGRAM_BOT_USERNAME": "DexSatoTestBot",
    "DEXSATO_TELEGRAM_WEBHOOK_SECRET": "a" * 40,
}


def test_disabled_gate_hides_both_routes():
    with patch.dict("os.environ", {}, clear=True):
        assert _client().post("/auth/telegram/link").status_code == 404
        assert _client().post("/telegram/link/webhook").status_code == 404


def test_issue_needs_origin_and_authenticated_product_user():
    principal = ProductPrincipal(True, uuid4())
    service = SimpleNamespace(issue=lambda *, user_id: "b" * 43)
    with (
        patch.dict("os.environ", _CONFIG, clear=True),
        patch("application.telegram_account_link_routes.product_auth_view", return_value=SimpleNamespace(principal=principal)),
        patch("application.telegram_account_link_routes.build_telegram_link_service", return_value=service),
    ):
        assert _client().post("/auth/telegram/link").status_code == 403
        accepted = _client().post("/auth/telegram/link", headers={"origin": "http://testserver"})
    assert accepted.status_code == 200
    assert accepted.headers["cache-control"] == "no-store"
    assert accepted.json()["url"] == "https://t.me/DexSatoTestBot?start=" + "b" * 43

    with (
        patch.dict("os.environ", _CONFIG, clear=True),
        patch("application.telegram_account_link_routes.product_auth_view", return_value=SimpleNamespace(principal=ProductPrincipal.guest())),
    ):
        assert _client().post("/auth/telegram/link", headers={"origin": "http://testserver"}).status_code == 401


def test_webhook_requires_secret_and_private_matching_sender():
    calls = []
    service = SimpleNamespace(redeem=lambda **kwargs: calls.append(kwargs) or True)
    update = {"message": {"chat": {"type": "private", "id": 123}, "from": {"id": 123}, "text": "/start " + "b" * 43}}
    with (
        patch.dict("os.environ", _CONFIG, clear=True),
        patch("application.telegram_account_link_routes.build_telegram_link_service", return_value=service),
    ):
        assert _client().post("/telegram/link/webhook", json=update).status_code == 401
        headers = {"X-Telegram-Bot-Api-Secret-Token": "a" * 40}
        group = {"message": {**update["message"], "chat": {"type": "group", "id": -100}}}
        assert _client().post("/telegram/link/webhook", headers=headers, json=group).json() == {"ok": True}
        mismatched = {"message": {**update["message"], "from": {"id": 999}}}
        assert _client().post("/telegram/link/webhook", headers=headers, json=mismatched).json() == {"ok": True}
        linked = _client().post("/telegram/link/webhook", headers=headers, json=update)
    assert linked.status_code == 200
    assert linked.json()["method"] == "sendMessage"
    assert calls == [{"token": "b" * 43, "telegram_user_id": 123, "chat_id": 123}]
