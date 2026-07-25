"""
AlphaRadar Telegram Notifier.

Supports two notification modes:

1. Legacy manual snapshot
   - Used by the current Founder Daily/manual endpoint
   - Sends the full supplied dashboard collection

2. Meaningful change digest
   - Used by Founder Automation
   - Sends only useful market changes
   - Remains silent when no meaningful changes exist

Environment variables
---------------------
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
ALPHARADAR_DASHBOARD_URL

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

import requests


# ==========================================================
# Configuration
# ==========================================================

DEFAULT_DASHBOARD_URL = (
    "http://127.0.0.1:8000"
)

MAX_DIGEST_CHANGES = 10


EVIDENCE_LABELS = {
    "ACCUMULATION": (
        "Buying pressure increasing"
    ),
    "DISTRIBUTION": (
        "Selling pressure increasing"
    ),
    "HIGH_VOLUME": (
        "Market volume increasing"
    ),
    "LIQUIDITY_UP": (
        "Liquidity increasing"
    ),
    "MOMENTUM": (
        "Momentum improving"
    ),
    "PRICE_BREAKOUT": (
        "Price breakout detected"
    ),
    "PRICE_MOMENTUM": (
        "Momentum improving"
    ),
    "PRICE_UP": (
        "Price momentum improving"
    ),
    "RISKY_ACTIVITY": (
        "Risky market activity detected"
    ),
    "STRONG_LIQUIDITY": (
        "Liquidity increasing"
    ),
    "VOLUME_UP": (
        "Trading activity increasing"
    ),
    "WEAK_MOMENTUM": (
        "Market momentum weakening"
    ),
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


def _resolve_dashboard_url(
    dashboard_url: str | None,
) -> str:
    """
    Resolve the dashboard URL used in Telegram messages.
    """

    resolved = (
        dashboard_url
        or os.getenv(
            "ALPHARADAR_DASHBOARD_URL",
        )
        or DEFAULT_DASHBOARD_URL
    )

    return resolved.rstrip(
        "/",
    )


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

    normalized = _normalize_text(
        reason,
        fallback="",
    ).upper()

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
# Meaningful Change Digest
# ==========================================================

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


def _build_single_change_lines(
    change: dict[str, object],
) -> list[str]:
    """
    Build one concise market-change section.
    """

    token = _normalize_text(
        change.get(
            "token",
        )
    ).upper()

    old_decision = _normalize_text(
        change.get(
            "old_decision",
        )
    ).upper()

    new_decision = _normalize_text(
        change.get(
            "new_decision",
        )
    ).upper()

    confidence = _normalize_text(
        change.get(
            "new_confidence",
        )
    ).upper()

    reasons = _meaningful_reasons(
        change,
    )

    lines = [
        f"{token} moved to {new_decision}",
        "",
    ]

    if (
        old_decision
        and old_decision != "UNKNOWN"
        and old_decision != new_decision
    ):

        lines.extend(
            [
                (
                    f"{old_decision} → "
                    f"{new_decision}"
                ),
                "",
            ]
        )

    if reasons:

        lines.append(
            "Why?",
        )

        lines.append(
            "",
        )

        for reason in reasons:

            lines.append(
                f"• {reason}"
            )

        lines.append(
            "",
        )

    lines.extend(
        [
            "Confidence",
            confidence,
            "",
            "Seen before",
        ]
    )

    if change.get(
        "seen_before",
        False,
    ) is True:

        historical = (
            _format_historical_success(
                change.get(
                    "historical_success",
                )
            )
        )

        lines.append(
            f"Yes ({historical})"
        )

    else:

        lines.append(
            "No — new market behaviour"
        )

    return lines


def build_change_digest_message(
    changes: list[dict[str, object]],
    *,
    dashboard_url: str | None = None,
    max_changes: int = MAX_DIGEST_CHANGES,
) -> str:
    """
    Build one actionable Telegram digest.

    Returns an empty string when no meaningful changes exist.
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

    resolved_dashboard_url = (
        _resolve_dashboard_url(
            dashboard_url,
        )
    )

    lines = [
        "📡 AlphaRadar",
        "",
    ]

    if len(
        selected,
    ) == 1:

        lines.extend(
            _build_single_change_lines(
                selected[0],
            )
        )

    else:

        lines.extend(
            [
                (
                    f"{len(selected)} "
                    "markets changed"
                ),
                "",
            ]
        )

        for index, change in enumerate(
            selected,
            start=1,
        ):

            if index > 1:

                lines.extend(
                    [
                        "",
                        "━━━━━━━━━━",
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
                (
                    f"+ {remaining} more "
                    "market changes"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "Open dashboard",
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

        decision = _normalize_text(
            item.get(
                "decision",
            )
        ).upper()

        confidence = _normalize_text(
            item.get(
                "confidence",
            )
        ).upper()

        historical = (
            _format_historical_success(
                item.get(
                    "historical_success",
                )
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

            for reason in reasons[:3]:

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