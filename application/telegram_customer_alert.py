"""Customer Telegram transport, admitted by the server-side Pro gate."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import requests

from application.telegram_notifier import _send_message
from application.telegram_pro_alert_gate import TelegramProAlertGate


def send_customer_telegram_alert(
    *,
    gate: TelegramProAlertGate,
    user_id: UUID,
    message: str,
    bot_token: str | None = None,
    post: Callable[..., object] = requests.post,
) -> bool:
    """Send only to a currently linked, active Pro user's private chat.

    Return False when the gate denies delivery; propagate transport failures.
    """
    if not isinstance(gate, TelegramProAlertGate):
        raise TypeError("a server-side Telegram Pro gate is required")

    def send(*, chat_id: int, message: str) -> None:
        _send_message(
            message=message,
            bot_token=bot_token,
            chat_id=str(chat_id),
            post=post,
        )

    return gate.deliver(user_id=user_id, message=message, send=send)