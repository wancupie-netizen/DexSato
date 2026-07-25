"""
AlphaRadar Meaningful Change Detector.

Compares two stored AlphaRadar snapshots and returns only
market changes that are useful for founder notifications.

Meaningful changes
------------------
- A decision changes into or out of an actionable state
- Confidence increases for an actionable decision
- New evidence appears for an actionable decision

Actionable decisions
--------------------
- BUY
- WATCH
- REVIEW
- SELL

This module does NOT:
- run market scans
- read or write snapshot files
- send Telegram messages
- schedule tasks
- render dashboard content
"""

from __future__ import annotations

from typing import Any


# ==========================================================
# Change Policy
# ==========================================================

ACTIONABLE_DECISIONS = frozenset(
    {
        "BUY",
        "WATCH",
        "REVIEW",
        "SELL",
    }
)


CONFIDENCE_RANK = {
    "UNKNOWN": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}


# ==========================================================
# Normalization
# ==========================================================

def _normalize_text(
    value: object,
    *,
    fallback: str = "UNKNOWN",
) -> str:
    """
    Normalize a value into uppercase comparison text.
    """

    normalized = str(
        value
        if value is not None
        else fallback
    ).strip().upper()

    return normalized or fallback


def _normalize_reasons(
    value: object,
) -> tuple[str, ...]:
    """
    Normalize evidence into a unique ordered tuple.
    """

    if not isinstance(
        value,
        list,
    ):

        return ()

    reasons: list[str] = []

    seen: set[str] = set()

    for raw_reason in value:

        reason = _normalize_text(
            raw_reason,
            fallback="",
        )

        if not reason:

            continue

        if reason in seen:

            continue

        seen.add(
            reason,
        )

        reasons.append(
            reason,
        )

    return tuple(
        reasons,
    )


# ==========================================================
# Snapshot Validation
# ==========================================================

def _snapshot_coins(
    snapshot: dict[str, Any],
) -> list[dict[str, object]]:
    """
    Return and validate the snapshot coin collection.
    """

    if not isinstance(
        snapshot,
        dict,
    ):

        raise ValueError(
            "Snapshot must be a dictionary."
        )

    coins = snapshot.get(
        "coins",
    )

    if not isinstance(
        coins,
        list,
    ):

        raise ValueError(
            "Snapshot coin data must be a list."
        )

    validated: list[dict[str, object]] = []

    for coin in coins:

        if not isinstance(
            coin,
            dict,
        ):

            raise ValueError(
                "Snapshot contains invalid coin data."
            )

        validated.append(
            coin,
        )

    return validated


def index_snapshot_coins(
    snapshot: dict[str, Any],
) -> dict[str, dict[str, object]]:
    """
    Index snapshot coin data by normalized token symbol.
    """

    indexed: dict[
        str,
        dict[str, object],
    ] = {}

    for coin in _snapshot_coins(
        snapshot,
    ):

        token = _normalize_text(
            coin.get(
                "token",
            )
        )

        if token in indexed:

            raise ValueError(
                "Snapshot contains duplicate token data: "
                f"{token}."
            )

        indexed[token] = coin

    return indexed


# ==========================================================
# Comparison Helpers
# ==========================================================

def confidence_increased(
    old_confidence: object,
    new_confidence: object,
) -> bool:
    """
    Return whether confidence moved to a higher level.
    """

    old_level = _normalize_text(
        old_confidence,
    )

    new_level = _normalize_text(
        new_confidence,
    )

    old_rank = CONFIDENCE_RANK.get(
        old_level,
        0,
    )

    new_rank = CONFIDENCE_RANK.get(
        new_level,
        0,
    )

    return new_rank > old_rank


def newly_added_reasons(
    old_reasons: object,
    new_reasons: object,
) -> list[str]:
    """
    Return evidence present only in the new snapshot.
    """

    normalized_old = set(
        _normalize_reasons(
            old_reasons,
        )
    )

    normalized_new = (
        _normalize_reasons(
            new_reasons,
        )
    )

    return [
        reason
        for reason in normalized_new
        if reason not in normalized_old
    ]


def decision_changed_meaningfully(
    old_decision: object,
    new_decision: object,
) -> bool:
    """
    Determine whether a decision transition matters.

    A transition matters when the decision changed and either
    the old or new state is actionable. This also preserves
    useful exit alerts such as WATCH -> IGNORE.
    """

    normalized_old = _normalize_text(
        old_decision,
    )

    normalized_new = _normalize_text(
        new_decision,
    )

    if normalized_old == normalized_new:

        return False

    return (
        normalized_old
        in ACTIONABLE_DECISIONS
        or normalized_new
        in ACTIONABLE_DECISIONS
    )


# ==========================================================
# Meaningful Change Detection
# ==========================================================

def detect_coin_change(
    *,
    old_coin: dict[str, object],
    new_coin: dict[str, object],
) -> dict[str, object] | None:
    """
    Detect one meaningful market change.

    Returns None when the change is not useful enough for an
    alert.
    """

    token = _normalize_text(
        new_coin.get(
            "token",
        )
    )

    old_available = old_coin.get(
        "available",
        False,
    ) is True

    new_available = new_coin.get(
        "available",
        False,
    ) is True

    if not old_available or not new_available:

        return None

    old_decision = _normalize_text(
        old_coin.get(
            "decision",
        )
    )

    new_decision = _normalize_text(
        new_coin.get(
            "decision",
        )
    )

    old_confidence = _normalize_text(
        old_coin.get(
            "confidence",
        )
    )

    new_confidence = _normalize_text(
        new_coin.get(
            "confidence",
        )
    )

    reasons_added = newly_added_reasons(
        old_coin.get(
            "reasons",
        ),
        new_coin.get(
            "reasons",
        ),
    )

    current_is_actionable = (
        new_decision
        in ACTIONABLE_DECISIONS
    )

    triggers: list[str] = []

    if decision_changed_meaningfully(
        old_decision,
        new_decision,
    ):

        triggers.append(
            "DECISION_CHANGED",
        )

    if (
        current_is_actionable
        and confidence_increased(
            old_confidence,
            new_confidence,
        )
    ):

        triggers.append(
            "CONFIDENCE_INCREASED",
        )

    if (
        current_is_actionable
        and reasons_added
    ):

        triggers.append(
            "EVIDENCE_ADDED",
        )

    if not triggers:

        return None

    historical_success_raw = new_coin.get(
        "historical_success",
        0.0,
    )

    try:

        historical_success = round(
            float(
                historical_success_raw
                if historical_success_raw
                is not None
                else 0.0
            ),
            2,
        )

    except (
        TypeError,
        ValueError,
    ):

        historical_success = 0.0

    return {
        "token": token,
        "old_decision": old_decision,
        "new_decision": new_decision,
        "old_confidence": old_confidence,
        "new_confidence": new_confidence,
        "reasons": list(
            _normalize_reasons(
                new_coin.get(
                    "reasons",
                )
            )
        ),
        "reasons_added": reasons_added,
        "historical_success": (
            historical_success
        ),
        "seen_before": (
            new_coin.get(
                "seen_before",
                False,
            )
            is True
        ),
        "summary": (
            str(
                new_coin.get(
                    "summary",
                    "",
                )
            ).strip()
        ),
        "triggers": triggers,
    }


def detect_meaningful_changes(
    *,
    previous_snapshot: dict[str, Any] | None,
    current_snapshot: dict[str, Any],
) -> list[dict[str, object]]:
    """
    Compare snapshots and return meaningful market changes.

    The first snapshot becomes the baseline and intentionally
    returns no changes, preventing initial Telegram spam.
    """

    current_coins = index_snapshot_coins(
        current_snapshot,
    )

    if previous_snapshot is None:

        return []

    previous_coins = index_snapshot_coins(
        previous_snapshot,
    )

    changes: list[dict[str, object]] = []

    for token, current_coin in current_coins.items():

        previous_coin = previous_coins.get(
            token,
        )

        if previous_coin is None:

            continue

        change = detect_coin_change(
            old_coin=previous_coin,
            new_coin=current_coin,
        )

        if change is not None:

            changes.append(
                change,
            )

    return changes