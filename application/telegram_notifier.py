"""
AlphaRadar Telegram Notifier.

Supports two notification modes:

1. Legacy manual snapshot
   - Used by Founder Daily and the manual API endpoint
   - Sends the full supplied dashboard collection

2. Meaningful change digest
   - Used by Founder Automation
   - Sends only useful market changes
   - Remains silent when no meaningful changes exist
   - Uses AlphaRadar Notification V1 format

Environment variables
---------------------
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
PUBLIC_DASHBOARD_URL

Dashboard URL policy
--------------------
Local addresses such as 127.0.0.1 and localhost are not
included in Telegram notifications because they cannot be
opened from another device.

A public dashboard URL may be added later through:

    PUBLIC_DASHBOARD_URL

This module does NOT:
- run market scans
- compare snapshots
- poll Telegram
- manage Telegram commands
- schedule alerts
- store credentials
"""

from __future__ import annotations

import os
from collections.abc import Callable
from urllib.parse import urlparse

import requests


# ==========================================================
# Configuration
# ==========================================================

MAX_DIGEST_CHANGES = 10

DIVIDER = "━━━━━━━━━━━━━━━━━━"


EVIDENCE_LABELS = {
    "ACCUMULATION": "Buying pressure increasing",
    "DISTRIBUTION": "Selling pressure increasing",
    "HIGH_VOLUME": "Market volume increasing",
    "LIQUIDITY_UP": "Liquidity increasing",
    "MOMENTUM": "Momentum improving",
    "PRICE_BREAKOUT": "Price breakout detected",
    "PRICE_MOMENTUM": "Momentum improving",
    "PRICE_UP": "Price momentum improving",
    "RISKY_ACTIVITY": "Risky market activity detected",
    "STRONG_LIQUIDITY": "Liquidity increasing",
    "VOLUME_UP": "Trading activity increasing",
    "WEAK_BREAKOUT": "Weak breakout",
    "WEAK_MOMENTUM": "Market momentum weakening",
}


DECISION_EMOJIS = {
    "BUY": "🟢",
    "WATCH": "🔵",
    "REVIEW": "🟡",
    "SELL": "🔴",
    "IGNORE": "⚪",
    "UNKNOWN": "⚪",
}


CONFIDENCE_EMOJIS = {
    "HIGH": "🟢",
    "MEDIUM": "🟡",
    "LOW": "🟠",
    "UNKNOWN": "⚪",
}


# ==========================================================
# Shared Helpers
# ==========================================================

def _normalize_text(
    value: object,
    *,
    fallback: str = "UNKNOWN",
) -> str:
    """
    Normalize one value for Telegram display.
    """

    text = str(
        value
        if value is not None
        else fallback
    ).strip()

    return text or fallback


def _normalize_upper(
    value: object,
    *,
    fallback: str = "UNKNOWN",
) -> str:
    """
    Normalize one value into uppercase display text.
    """

    return _normalize_text(
        value,
        fallback=fallback,
    ).upper()


def _resolve_credentials(
    *,
    bot_token: str | None,
    chat_id: str | None,
) -> tuple[str, str]:
    """
    Resolve and validate Telegram credentials.
    """

    resolved_bot_token = (
        bot_token
        or os.getenv(
            "TELEGRAM_BOT_TOKEN",
        )
    )

    resolved_chat_id = (
        chat_id
        or os.getenv(
            "TELEGRAM_CHAT_ID",
        )
    )

    if not resolved_bot_token:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not configured."
        )

    if not resolved_chat_id:

        raise RuntimeError(
            "TELEGRAM_CHAT_ID is not configured."
        )

    return (
        resolved_bot_token,
        resolved_chat_id,
    )


def _resolve_public_dashboard_url(
    dashboard_url: str | None,
) -> str | None:
    """
    Return a usable public dashboard URL.

    Localhost and loopback addresses are intentionally hidden
    because Telegram users on other devices cannot open them.
    """

    configured = (
        dashboard_url
        or os.getenv(
            "PUBLIC_DASHBOARD_URL",
        )
    )

    if not configured:

        return None

    resolved = str(
        configured,
    ).strip().rstrip(
        "/",
    )

    if not resolved:

        return None

    parsed = urlparse(
        resolved,
    )

    hostname = (
        parsed.hostname
        or ""
    ).strip().lower()

    if hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
        "0.0.0.0",
    }:

        return None

    if parsed.scheme not in {
        "http",
        "https",
    }:

        return None

    return resolved


def _send_message(
    *,
    message: str,
    bot_token: str | None = None,
    chat_id: str | None = None,
    post: Callable[..., object] = requests.post,
) -> dict[str, object]:
    """
    Send one plain-text Telegram message.
    """

    if not isinstance(
        message,
        str,
    ) or not message.strip():

        raise ValueError(
            "Telegram message must not be empty."
        )

    (
        resolved_bot_token,
        resolved_chat_id,
    ) = _resolve_credentials(
        bot_token=bot_token,
        chat_id=chat_id,
    )

    url = (
        "https://api.telegram.org/"
        f"bot{resolved_bot_token}/sendMessage"
    )

    response = post(
        url,
        json={
            "chat_id": resolved_chat_id,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=15,
    )

    response.raise_for_status()

    return {
        "success": True,
        "sent": True,
        "chat_id": resolved_chat_id,
    }


# ==========================================================
# Evidence Translation
# ==========================================================

def humanize_evidence(
    reason: object,
) -> str:
    """
    Convert technical evidence into natural language.
    """

    normalized = _normalize_upper(
        reason,
        fallback="",
    )

    if not normalized:

        return ""

    mapped = EVIDENCE_LABELS.get(
        normalized,
    )

    if mapped:

        return mapped

    return normalized.replace(
        "_",
        " ",
    ).strip().capitalize()


def _meaningful_reasons(
    change: dict[str, object],
) -> list[str]:
    """
    Select evidence appropriate for one alert.

    Newly added evidence is preferred. Full current evidence
    is used as a fallback.
    """

    reasons_added = change.get(
        "reasons_added",
    )

    if isinstance(
        reasons_added,
        list,
    ) and reasons_added:

        source = reasons_added

    else:

        current_reasons = change.get(
            "reasons",
        )

        source = (
            current_reasons
            if isinstance(
                current_reasons,
                list,
            )
            else []
        )

    translated: list[str] = []

    seen: set[str] = set()

    for raw_reason in source:

        reason = humanize_evidence(
            raw_reason,
        )

        if not reason:

            continue

        if reason in seen:

            continue

        seen.add(
            reason,
        )

        translated.append(
            reason,
        )

        if len(
            translated,
        ) == 3:

            break

    return translated


# ==========================================================
# Notification Presentation
# ==========================================================

def _decision_emoji(
    decision: object,
) -> str:
    """
    Return the visual indicator for one decision.
    """

    normalized = _normalize_upper(
        decision,
    )

    return DECISION_EMOJIS.get(
        normalized,
        "⚪",
    )


def _confidence_emoji(
    confidence: object,
) -> str:
    """
    Return the visual indicator for one confidence level.
    """

    normalized = _normalize_upper(
        confidence,
    )

    return CONFIDENCE_EMOJIS.get(
        normalized,
        "⚪",
    )


def _activity_emoji(
    change_count: int,
) -> str:
    """
    Return the Radar Activity indicator.
    """

    if change_count >= 6:

        return "🔴"

    if change_count >= 3:

        return "🟠"

    return "🟡"


def _market_label(
    count: int,
) -> str:
    """
    Return a correctly pluralized market-change label.
    """

    if count == 1:

        return "1 market changed"

    return f"{count} markets changed"


def _format_historical_success(
    value: object,
) -> str:
    """
    Format historical success safely.
    """

    try:

        result = float(
            value
            if value is not None
            else 0.0
        )

    except (
        TypeError,
        ValueError,
    ):

        result = 0.0

    return f"{result:.0f}%"


def _build_history_line(
    change: dict[str, object],
) -> str:
    """
    Build the human-readable history status.
    """

    if change.get(
        "seen_before",
        False,
    ) is not True:

        return "🆕 New pattern"

    historical = _format_historical_success(
        change.get(
            "historical_success",
        )
    )

    return (
        "📚 Seen before"
        f" · {historical} historical success"
    )


def _build_single_change_lines(
    change: dict[str, object],
) -> list[str]:
    """
    Build one AlphaRadar Notification V1 market section.
    """

    token = _normalize_upper(
        change.get(
            "token",
        )
    )

    old_decision = _normalize_upper(
        change.get(
            "old_decision",
        )
    )

    new_decision = _normalize_upper(
        change.get(
            "new_decision",
        )
    )

    confidence = _normalize_upper(
        change.get(
            "new_confidence",
        )
    )

    reasons = _meaningful_reasons(
        change,
    )

    decision_icon = _decision_emoji(
        new_decision,
    )

    confidence_icon = _confidence_emoji(
        confidence,
    )

    lines = [
        f"{decision_icon} {token}",
        "",
        "Status",
        "",
        (
            f"{old_decision} → "
            f"{new_decision}"
        ),
        "",
        DIVIDER,
        "",
        "Why?",
        "",
    ]

    if reasons:

        for reason in reasons:

            lines.append(
                f"• {reason}"
            )

    else:

        lines.append(
            "• Market evidence changed"
        )

    lines.extend(
        [
            "",
            DIVIDER,
            "",
            "Confidence",
            "",
            (
                f"{confidence_icon} "
                f"{confidence}"
            ),
            "",
            DIVIDER,
            "",
            "History",
            "",
            _build_history_line(
                change,
            ),
        ]
    )

    return lines


# ==========================================================
# Meaningful Change Digest
# ==========================================================

def build_change_digest_message(
    changes: list[dict[str, object]],
    *,
    dashboard_url: str | None = None,
    max_changes: int = MAX_DIGEST_CHANGES,
) -> str:
    """
    Build one actionable AlphaRadar Notification V1 digest.

    Returns an empty string when no meaningful changes exist.
    Local dashboard URLs are intentionally omitted.
    """

    if not isinstance(
        changes,
        list,
    ):

        raise ValueError(
            "Changes must be a list."
        )

    if not isinstance(
        max_changes,
        int,
    ) or max_changes < 1:

        raise ValueError(
            "Maximum digest changes must be at least one."
        )

    if not changes:

        return ""

    validated: list[
        dict[str, object]
    ] = []

    for change in changes:

        if not isinstance(
            change,
            dict,
        ):

            raise ValueError(
                "Changes contain invalid data."
            )

        validated.append(
            change,
        )

    selected = validated[
        :max_changes
    ]

    lines = [
        "📡 AlphaRadar",
        "",
        "Radar detected a market shift.",
        "",
        DIVIDER,
        "",
    ]

    for index, change in enumerate(
        selected,
    ):

        if index > 0:

            lines.extend(
                [
                    "",
                    DIVIDER,
                    "",
                ]
            )

        lines.extend(
            _build_single_change_lines(
                change,
            )
        )

    remaining = (
        len(validated)
        - len(selected)
    )

    if remaining > 0:

        lines.extend(
            [
                "",
                DIVIDER,
                "",
                (
                    f"+ {remaining} more "
                    "market changes"
                ),
            ]
        )

    change_count = len(
        validated,
    )

    lines.extend(
        [
            "",
            DIVIDER,
            "",
            "Radar Activity",
            "",
            (
                f"{_activity_emoji(change_count)} "
                f"{_market_label(change_count)}"
            ),
        ]
    )

    resolved_dashboard_url = (
        _resolve_public_dashboard_url(
            dashboard_url,
        )
    )

    if resolved_dashboard_url:

        lines.extend(
            [
                "",
                DIVIDER,
                "",
                "Open dashboard",
                "",
                resolved_dashboard_url,
            ]
        )

    return "\n".join(
        lines,
    )


def send_change_digest(
    *,
    changes: list[dict[str, object]],
    dashboard_url: str | None = None,
    max_changes: int = MAX_DIGEST_CHANGES,
    bot_token: str | None = None,
    chat_id: str | None = None,
    post: Callable[..., object] = requests.post,
) -> dict[str, object]:
    """
    Send meaningful changes only.

    No Telegram API request is made when changes are empty.
    """

    message = build_change_digest_message(
        changes,
        dashboard_url=dashboard_url,
        max_changes=max_changes,
    )

    if not message:

        return {
            "success": True,
            "sent": False,
            "changes": 0,
        }

    result = _send_message(
        message=message,
        bot_token=bot_token,
        chat_id=chat_id,
        post=post,
    )

    return {
        **result,
        "changes": min(
            len(changes),
            max_changes,
        ),
    }


# ==========================================================
# Legacy Manual Full Snapshot
# ==========================================================

def build_telegram_message(
    dashboard_data: list[dict[str, object]],
) -> str:
    """
    Build the legacy manual full-snapshot message.

    This remains available for backward compatibility with
    Founder Daily and the manual FastAPI endpoint.
    """

    if not isinstance(
        dashboard_data,
        list,
    ):

        raise ValueError(
            "Dashboard data must be a list."
        )

    lines = [
        "🚨 AlphaRadar Founder Alert",
        "",
        (
            f"{len(dashboard_data)} markets. "
            "One engine."
        ),
    ]

    for item in dashboard_data:

        if not isinstance(
            item,
            dict,
        ):

            raise ValueError(
                "Dashboard data contains invalid market data."
            )

        token = _normalize_text(
            item.get(
                "token",
            )
        )

        lines.extend(
            [
                "",
                f"🔹 {token}",
            ]
        )

        if not item.get(
            "available",
            False,
        ):

            lines.append(
                "Status: UNAVAILABLE"
            )

            error = item.get(
                "error",
            )

            if error:

                lines.append(
                    f"Reason: {error}"
                )

            continue

        decision = _normalize_upper(
            item.get(
                "decision",
            )
        )

        confidence = _normalize_upper(
            item.get(
                "confidence",
            )
        )

        historical = _format_historical_success(
            item.get(
                "historical_success",
            )
        )

        lines.extend(
            [
                f"Decision: {decision}",
                f"Confidence: {confidence}",
                (
                    "Historical Success: "
                    f"{historical}"
                ),
                (
                    "Adaptive Memory: "
                    + (
                        "KNOWN PATTERN"
                        if item.get(
                            "seen_before",
                            False,
                        )
                        else "NEW PATTERN"
                    )
                ),
            ]
        )

        reasons = item.get(
            "reasons",
            [],
        )

        if isinstance(
            reasons,
            list,
        ) and reasons:

            lines.append(
                "Evidence:"
            )

            for reason in reasons[
                :3
            ]:

                lines.append(
                    (
                        "• "
                        f"{humanize_evidence(reason)}"
                    )
                )

        else:

            lines.append(
                "Evidence: None available"
            )

    lines.extend(
        [
            "",
            (
                "AlphaRadar · "
                "Engine-driven market intelligence"
            ),
        ]
    )

    return "\n".join(
        lines,
    )


def send_telegram_alert(
    *,
    dashboard_data: list[dict[str, object]],
    bot_token: str | None = None,
    chat_id: str | None = None,
    post: Callable[..., object] = requests.post,
) -> dict[str, object]:
    """
    Send the legacy manual full snapshot to Telegram.
    """

    message = build_telegram_message(
        dashboard_data,
    )

    result = _send_message(
        message=message,
        bot_token=bot_token,
        chat_id=chat_id,
        post=post,
    )

    return {
        "success": True,
        "chat_id": result[
            "chat_id"
        ],
        "coins": len(
            dashboard_data,
        ),
    }