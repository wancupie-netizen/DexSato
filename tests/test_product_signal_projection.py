from __future__ import annotations

import pytest

from application.product_signal_entitlement import ProductSignalEntitlementAdmission
from application.product_signal_projection import (
    collect_detected_signal_token_addresses,
    project_detected_signal_entitlements,
)


def _signal(label: str) -> dict[str, object]:
    return {
        "primary_signal": label,
        "secondary_evidence": ["Volume ↑"],
        "direction": "bullish",
    }


def _row(token: str, *, signal: object = None, rank: int = 1) -> dict[str, object]:
    row: dict[str, object] = {
        "token_address": token,
        "rank": rank,
        "symbol": token,
        "price_usd": 1.0,
    }
    if signal is not None:
        row["detected_signal"] = signal
    return row


def _admission(*allowed: str) -> ProductSignalEntitlementAdmission:
    return ProductSignalEntitlementAdmission(
        allowed_token_addresses=tuple(allowed),
        newly_admitted_token_addresses=tuple(allowed),
        quota_limit=5,
        active_count=len(allowed),
        remaining=max(0, 5 - len(allowed)),
    )


def test_collects_signals_in_locked_market_view_order_and_dedupes_tokens() -> None:
    feeds = {
        "recent": {"rows": [_row("MintD", signal=_signal("D"))]},
        "organic_flow": {
            "rows": [
                _row("MintC", signal=_signal("C")),
                _row("MintA", signal=_signal("A duplicate")),
            ]
        },
        "top_traded": {"rows": [_row("MintB", signal=_signal("B"))]},
        "trending": {"rows": [_row("MintA", signal=_signal("A"))]},
    }

    assert collect_detected_signal_token_addresses(feeds) == (
        "MintA",
        "MintB",
        "MintC",
        "MintD",
    )


def test_collects_future_extra_feeds_after_canonical_views_deterministically() -> None:
    feeds = {
        "zeta": {"rows": [_row("MintZ", signal=_signal("Z"))]},
        "trending": {"rows": [_row("MintA", signal=_signal("A"))]},
        "alpha": {"rows": [_row("MintX", signal=_signal("X"))]},
    }

    assert collect_detected_signal_token_addresses(feeds) == (
        "MintA",
        "MintX",
        "MintZ",
    )


def test_collection_ignores_rows_without_active_signal() -> None:
    feeds = {
        "trending": {
            "rows": [
                _row("MintA"),
                _row("MintB", signal={"primary_signal": ""}),
                _row("MintC", signal=""),
                _row("MintD", signal=_signal("D")),
            ]
        }
    }

    assert collect_detected_signal_token_addresses(feeds) == ("MintD",)


def test_collection_skips_invalid_signal_token_addresses_fail_closed() -> None:
    feeds = {
        "trending": {
            "rows": [
                _row(" MintA", signal=_signal("A")),
                _row("Mint B", signal=_signal("B")),
                {"token_address": None, "detected_signal": _signal("C")},
                _row("MintD", signal=_signal("D")),
            ]
        }
    }

    assert collect_detected_signal_token_addresses(feeds) == ("MintD",)


def test_projection_preserves_allowed_signal_and_hides_non_admitted_signal() -> None:
    allowed = _row("MintA", signal=_signal("A"), rank=1)
    hidden = _row("MintB", signal=_signal("B"), rank=2)
    feeds = {
        "trending": {
            "connected": True,
            "eligible_count": 2,
            "rows": [allowed, hidden],
        }
    }

    projected = project_detected_signal_entitlements(feeds, _admission("MintA"))
    rows = projected["trending"]["rows"]

    assert rows[0]["detected_signal"] == _signal("A")
    assert "detected_signal" not in rows[1]
    assert [row["token_address"] for row in rows] == ["MintA", "MintB"]
    assert [row["rank"] for row in rows] == [1, 2]
    assert projected["trending"]["eligible_count"] == 2


def test_projection_keeps_same_token_signal_across_multiple_views_when_admitted() -> None:
    feeds = {
        "trending": {"rows": [_row("MintA", signal=_signal("Trend"))]},
        "top_traded": {"rows": [_row("MintA", signal=_signal("Top"))]},
        "organic_flow": {"rows": [_row("MintB", signal=_signal("Organic"))]},
    }

    projected = project_detected_signal_entitlements(feeds, _admission("MintA"))

    assert "detected_signal" in projected["trending"]["rows"][0]
    assert "detected_signal" in projected["top_traded"]["rows"][0]
    assert "detected_signal" not in projected["organic_flow"]["rows"][0]


def test_projection_does_not_remove_rows_or_change_feed_metadata() -> None:
    feeds = {
        "trending": {
            "connected": True,
            "status": "live",
            "eligible_count": 3,
            "source": "jupiter",
            "rows": [
                _row("MintA", signal=_signal("A"), rank=1),
                _row("MintB", signal=_signal("B"), rank=2),
                _row("MintC", rank=3),
            ],
        }
    }

    projected = project_detected_signal_entitlements(feeds, _admission("MintA"))

    assert len(projected["trending"]["rows"]) == 3
    assert projected["trending"]["connected"] is True
    assert projected["trending"]["status"] == "live"
    assert projected["trending"]["eligible_count"] == 3
    assert projected["trending"]["source"] == "jupiter"


def test_projection_never_mutates_loaded_market_feeds() -> None:
    signal = _signal("B")
    hidden = _row("MintB", signal=signal)
    feeds = {"trending": {"rows": [hidden]}}

    projected = project_detected_signal_entitlements(feeds, _admission())

    assert feeds["trending"]["rows"][0]["detected_signal"] is signal
    assert "detected_signal" not in projected["trending"]["rows"][0]
    assert projected["trending"] is not feeds["trending"]
    assert projected["trending"]["rows"][0] is not feeds["trending"]["rows"][0]


def test_projection_reuses_unchanged_feed_payload_without_mutation() -> None:
    feeds = {
        "trending": {"rows": [_row("MintA", signal=_signal("A"))]},
        "status": "metadata",
    }

    projected = project_detected_signal_entitlements(feeds, _admission("MintA"))

    assert projected["trending"] is feeds["trending"]
    assert projected["status"] == "metadata"


def test_projection_hides_signal_with_invalid_or_missing_token_address() -> None:
    feeds = {
        "trending": {
            "rows": [
                _row(" MintA", signal=_signal("A")),
                {"symbol": "UNKNOWN", "detected_signal": _signal("B")},
            ]
        }
    }

    projected = project_detected_signal_entitlements(feeds, _admission("MintA"))

    assert "detected_signal" not in projected["trending"]["rows"][0]
    assert "detected_signal" not in projected["trending"]["rows"][1]


def test_projection_with_empty_admission_hides_all_active_signals_only() -> None:
    no_signal = _row("MintC")
    feeds = {
        "trending": {
            "rows": [
                _row("MintA", signal=_signal("A")),
                _row("MintB", signal="Legacy signal"),
                no_signal,
            ]
        }
    }

    projected = project_detected_signal_entitlements(feeds, _admission())
    rows = projected["trending"]["rows"]

    assert "detected_signal" not in rows[0]
    assert "detected_signal" not in rows[1]
    assert rows[2] is no_signal


def test_projection_requires_reviewed_types() -> None:
    with pytest.raises(TypeError, match="market_feeds"):
        collect_detected_signal_token_addresses([])
    with pytest.raises(TypeError, match="market_feeds"):
        project_detected_signal_entitlements([], _admission())
    with pytest.raises(TypeError, match="admission"):
        project_detected_signal_entitlements({}, object())
