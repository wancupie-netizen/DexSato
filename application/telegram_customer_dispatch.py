"""Opt-in customer fanout from the founder automation's ALERT changes."""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from application.product_identity_runtime import (
    _default_create_client,
    build_telegram_pro_alert_gate,
    product_identity_runtime_config,
)
from application.telegram_customer_alert import send_customer_telegram_alert
from application.telegram_notifier import _alert_changes, _build_alert_lines


def customer_alerts_enabled() -> bool:
    value = os.getenv("DEXSATO_CUSTOMER_TELEGRAM_ALERTS_ENABLED", "false").strip().casefold()
    if value in {"", "0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    raise RuntimeError("DEXSATO_CUSTOMER_TELEGRAM_ALERTS_ENABLED must be boolean.")


def customer_change_message(changes: list[dict[str, object]]) -> str:
    if not isinstance(changes, list) or any(not isinstance(row, dict) for row in changes):
        raise ValueError("Invalid customer alert changes.")
    alerts = _alert_changes(changes)
    if not alerts:
        return ""
    lines = ["🚨 DexSato Market Alert", "", f"{len(alerts)} market(s) require attention"]
    for change in alerts[:10]:
        lines.extend(["", *_build_alert_lines(change)])
    if len(alerts) > 10:
        lines.extend(["", f"+{len(alerts) - 10} additional alerts in DexSato"])
    return "\n".join(lines)


def linked_customer_ids(client: Any, *, page_size: int = 100) -> list[UUID]:
    """Collect ordered linked identities before sending any alert."""
    if not 1 <= page_size <= 100:
        raise ValueError("page_size must be between 1 and 100")

    identities: list[UUID] = []
    previous: str | None = None

    while True:
        query = client.table("dexsato_telegram_account_links").select("user_id")
        if previous is not None:
            query = query.gt("user_id", previous)

        rows = getattr(query.order("user_id").limit(page_size).execute(), "data", None)
        if not isinstance(rows, list) or len(rows) > page_size:
            raise RuntimeError("Invalid Telegram recipient page.")

        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("user_id"), str):
                raise RuntimeError("Invalid Telegram recipient identity.")
            try:
                user = UUID(row["user_id"])
            except ValueError as error:
                raise RuntimeError("Invalid Telegram recipient identity.") from error

            canonical = str(user)
            if row["user_id"] != canonical or (
                previous is not None and canonical <= previous
            ):
                raise RuntimeError("Unordered Telegram recipient page.")

            identities.append(user)
            previous = canonical

        if len(rows) < page_size:
            return identities


def deliver_customer_changes(*, changes: list[dict[str, object]]) -> dict[str, int | str]:
    """Keep customer fanout inert until the separate rollout flag is enabled."""
    if not customer_alerts_enabled():
        return {"status": "DISABLED", "sent": 0, "failed": 0}

    message = customer_change_message(changes)
    if not message:
        return {"status": "SKIPPED", "sent": 0, "failed": 0}

    config = product_identity_runtime_config()
    if not config.enabled:
        raise RuntimeError("Product authentication is disabled.")

    client = _default_create_client(config.supabase_url, config.secret_key)
    user_ids = linked_customer_ids(client)
    gate = build_telegram_pro_alert_gate()

    sent = failed = 0
    for user_id in user_ids:
        try:
            sent += int(
                send_customer_telegram_alert(
                    gate=gate,
                    user_id=user_id,
                    message=message,
                )
            )
        except Exception:
            failed += 1

    return {
        "status": "FAILED" if failed else "SENT" if sent else "SKIPPED",
        "sent": sent,
        "failed": failed,
    }
