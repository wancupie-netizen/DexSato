"""
Tests for DexSato Meaningful Change Detector.
"""

import pytest

from application.change_detector import (
    ACTIONABLE_DECISIONS,
    confidence_increased,
    decision_changed_meaningfully,
    detect_meaningful_changes,
    index_snapshot_coins,
    newly_added_reasons,
)


def build_coin(
    token: str,
    *,
    decision: str = "IGNORE",
    confidence: str = "LOW",
    reasons: list[str] | None = None,
    available: bool = True,
    historical_success: float = 0.0,
    seen_before: bool = False,
) -> dict[str, object]:
    """
    Build reusable serialized snapshot coin data.
    """

    return {
        "token": token,
        "available": available,
        "decision": (
            decision
            if available
            else None
        ),
        "confidence": (
            confidence
            if available
            else None
        ),
        "historical_success": (
            historical_success
            if available
            else None
        ),
        "seen_before": seen_before,
        "reasons": (
            reasons
            if reasons is not None
            else []
        ),
        "summary": (
            f"Recommended action: {decision}"
            if available
            else None
        ),
        "error": (
            None
            if available
            else "Unavailable."
        ),
    }


def build_snapshot(
    *coins: dict[str, object],
) -> dict[str, object]:
    """
    Build one reusable snapshot payload.
    """

    available_count = sum(
        1
        for coin in coins
        if coin["available"] is True
    )

    return {
        "generated_at": (
            "2026-07-25T00:00:00+00:00"
        ),
        "total_coins": len(
            coins,
        ),
        "available_coins": available_count,
        "unavailable_coins": (
            len(coins)
            - available_count
        ),
        "coins": list(
            coins,
        ),
    }


def test_should_define_actionable_decisions():
    """
    Only useful market decisions are actionable.
    """

    assert ACTIONABLE_DECISIONS == {
        "BUY",
        "WATCH",
        "REVIEW",
        "SELL",
    }


def test_should_detect_confidence_increase():
    """
    Confidence should trigger only when moving higher.
    """

    assert confidence_increased(
        "LOW",
        "MEDIUM",
    ) is True

    assert confidence_increased(
        "MEDIUM",
        "HIGH",
    ) is True

    assert confidence_increased(
        "LOW",
        "HIGH",
    ) is True

    assert confidence_increased(
        "HIGH",
        "MEDIUM",
    ) is False

    assert confidence_increased(
        "LOW",
        "LOW",
    ) is False


def test_should_detect_new_evidence():
    """
    Only evidence absent from the old snapshot is returned.
    """

    reasons = newly_added_reasons(
        [
            "MOMENTUM",
        ],
        [
            "MOMENTUM",
            "STRONG_LIQUIDITY",
        ],
    )

    assert reasons == [
        "STRONG_LIQUIDITY",
    ]


def test_should_detect_actionable_decision_change():
    """
    IGNORE to WATCH should be a meaningful transition.
    """

    assert decision_changed_meaningfully(
        "IGNORE",
        "WATCH",
    ) is True

    assert decision_changed_meaningfully(
        "WATCH",
        "IGNORE",
    ) is True

    assert decision_changed_meaningfully(
        "IGNORE",
        "IGNORE",
    ) is False


def test_should_treat_first_snapshot_as_baseline():
    """
    Initial snapshot must not create ten Telegram alerts.
    """

    current = build_snapshot(
        build_coin(
            "BTC",
            decision="WATCH",
            confidence="HIGH",
        ),
    )

    changes = detect_meaningful_changes(
        previous_snapshot=None,
        current_snapshot=current,
    )

    assert changes == []


def test_should_detect_ignore_to_watch():
    """
    A coin entering WATCH should produce one change.
    """

    previous = build_snapshot(
        build_coin(
            "BTC",
            decision="IGNORE",
            confidence="LOW",
        ),
    )

    current = build_snapshot(
        build_coin(
            "BTC",
            decision="WATCH",
            confidence="HIGH",
            reasons=[
                "MOMENTUM",
                "STRONG_LIQUIDITY",
            ],
            historical_success=82.0,
            seen_before=True,
        ),
    )

    changes = detect_meaningful_changes(
        previous_snapshot=previous,
        current_snapshot=current,
    )

    assert len(
        changes,
    ) == 1

    change = changes[0]

    assert change["token"] == "BTC"

    assert change["old_decision"] == (
        "IGNORE"
    )

    assert change["new_decision"] == (
        "WATCH"
    )

    assert change["new_confidence"] == (
        "HIGH"
    )

    assert change["historical_success"] == (
        82.0
    )

    assert change["seen_before"] is True

    assert change["reasons_added"] == [
        "MOMENTUM",
        "STRONG_LIQUIDITY",
    ]

    assert change["triggers"] == [
        "DECISION_CHANGED",
        "CONFIDENCE_INCREASED",
        "EVIDENCE_ADDED",
    ]


def test_should_ignore_unchanged_ignore_market():
    """
    Repeated IGNORE results should remain silent.
    """

    previous = build_snapshot(
        build_coin(
            "BTC",
            decision="IGNORE",
            confidence="LOW",
        ),
    )

    current = build_snapshot(
        build_coin(
            "BTC",
            decision="IGNORE",
            confidence="LOW",
        ),
    )

    changes = detect_meaningful_changes(
        previous_snapshot=previous,
        current_snapshot=current,
    )

    assert changes == []


def test_should_detect_confidence_increase_for_watch():
    """
    WATCH confidence increasing should be meaningful.
    """

    previous = build_snapshot(
        build_coin(
            "ETH",
            decision="WATCH",
            confidence="MEDIUM",
            reasons=[
                "MOMENTUM",
            ],
        ),
    )

    current = build_snapshot(
        build_coin(
            "ETH",
            decision="WATCH",
            confidence="HIGH",
            reasons=[
                "MOMENTUM",
            ],
        ),
    )

    changes = detect_meaningful_changes(
        previous_snapshot=previous,
        current_snapshot=current,
    )

    assert len(
        changes,
    ) == 1

    assert changes[0]["triggers"] == [
        "CONFIDENCE_INCREASED",
    ]


def test_should_detect_new_evidence_for_review():
    """
    New evidence on REVIEW should be meaningful.
    """

    previous = build_snapshot(
        build_coin(
            "ETH",
            decision="REVIEW",
            confidence="MEDIUM",
            reasons=[
                "DISTRIBUTION",
            ],
        ),
    )

    current = build_snapshot(
        build_coin(
            "ETH",
            decision="REVIEW",
            confidence="MEDIUM",
            reasons=[
                "DISTRIBUTION",
                "RISKY_ACTIVITY",
            ],
        ),
    )

    changes = detect_meaningful_changes(
        previous_snapshot=previous,
        current_snapshot=current,
    )

    assert len(
        changes,
    ) == 1

    assert changes[0]["reasons_added"] == [
        "RISKY_ACTIVITY",
    ]

    assert changes[0]["triggers"] == [
        "EVIDENCE_ADDED",
    ]


def test_should_ignore_confidence_change_on_ignore():
    """
    IGNORE markets should not alert only because confidence
    changed.
    """

    previous = build_snapshot(
        build_coin(
            "BTC",
            decision="IGNORE",
            confidence="LOW",
        ),
    )

    current = build_snapshot(
        build_coin(
            "BTC",
            decision="IGNORE",
            confidence="HIGH",
        ),
    )

    changes = detect_meaningful_changes(
        previous_snapshot=previous,
        current_snapshot=current,
    )

    assert changes == []


def test_should_ignore_newly_added_token():
    """
    New tokens should establish a baseline without alerting.
    """

    previous = build_snapshot(
        build_coin(
            "BTC",
        ),
    )

    current = build_snapshot(
        build_coin(
            "BTC",
        ),
        build_coin(
            "ETH",
            decision="WATCH",
            confidence="HIGH",
        ),
    )

    changes = detect_meaningful_changes(
        previous_snapshot=previous,
        current_snapshot=current,
    )

    assert changes == []


def test_should_reject_duplicate_token_data():
    """
    Duplicate token entries make comparison ambiguous.
    """

    snapshot = build_snapshot(
        build_coin(
            "BTC",
        ),
        build_coin(
            "BTC",
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "duplicate token data: BTC"
        ),
    ):

        index_snapshot_coins(
            snapshot,
        )


def test_should_reject_invalid_snapshot():
    """
    Snapshot must contain a list of coin dictionaries.
    """

    with pytest.raises(
        ValueError,
        match=(
            "Snapshot must be a dictionary"
        ),
    ):

        detect_meaningful_changes(
            previous_snapshot=None,
            current_snapshot=None,
        )

    with pytest.raises(
        ValueError,
        match=(
            "Snapshot coin data must be a list"
        ),
    ):

        detect_meaningful_changes(
            previous_snapshot=None,
            current_snapshot={
                "coins": None,
            },
        )