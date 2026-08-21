"""Evaluate price follow-through after a recorded directional 4H bias."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


FOLLOW_THROUGH_THRESHOLD_PCT = 0.5
HORIZONS = (("4H", timedelta(hours=4)), ("24H", timedelta(hours=24)))
DIRECTIONAL_BIASES = {"BULLISH_DEVELOPING", "BEARISH_DEVELOPING"}


def _time(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _assessment(bias: str, price_change_pct: float) -> str:
    threshold = FOLLOW_THROUGH_THRESHOLD_PCT
    if abs(price_change_pct) < threshold:
        return "INCONCLUSIVE"
    supportive = (
        bias == "BULLISH_DEVELOPING" and price_change_pct >= threshold
    ) or (
        bias == "BEARISH_DEVELOPING" and price_change_pct <= -threshold
    )
    return "SUPPORTIVE" if supportive else "CONTRADICTED"


def build_evidence_follow_through(
    history: object,
) -> dict[str, object]:
    """Evaluate fixed horizons from bounded scan history, without P&L claims."""
    if not isinstance(history, list):
        history = []
    points = [dict(point) for point in history if isinstance(point, dict)]
    points.sort(key=lambda point: str(point.get("recorded_at", "")))
    if not points:
        return {
            "status": "COLLECTING", "evaluations": [],
            "message": "Collecting sufficient scan history.",
            "policy": "Evidence follow-through only; not win rate, P&L or trade advice.",
        }
    latest = points[-1]
    latest_at = _time(latest.get("recorded_at"))
    latest_price = _number(latest.get("price"))
    evaluations = []
    if latest_at is not None and latest_price is not None:
        for label, duration in HORIZONS:
            cutoff = latest_at - duration
            eligible = [
                point for point in points[:-1]
                if (_time(point.get("recorded_at")) or latest_at) <= cutoff
                and str(point.get("technical_bias", "")).upper() in DIRECTIONAL_BIASES
                and _number(point.get("price")) not in {None, 0.0}
            ]
            if not eligible:
                continue
            anchor = eligible[-1]
            anchor_price = _number(anchor.get("price"))
            if anchor_price in {None, 0.0}:
                continue
            change = (latest_price / anchor_price - 1) * 100
            bias = str(anchor.get("technical_bias")).upper()
            assessment = _assessment(bias, change)
            evaluations.append({
                "horizon": label,
                "assessment": assessment,
                "recorded_bias": bias,
                "anchor_at": str(anchor.get("recorded_at")),
                "anchor_price": round(anchor_price, 8),
                "current_at": str(latest.get("recorded_at")),
                "current_price": round(latest_price, 8),
                "price_change_pct": round(change, 2),
                "threshold_pct": FOLLOW_THROUGH_THRESHOLD_PCT,
            })
    return {
        "status": "AVAILABLE" if evaluations else "COLLECTING",
        "evaluations": evaluations,
        "message": (
            "Price follow-through after previously recorded directional evidence."
            if evaluations else "Collecting sufficient scan history."
        ),
        "policy": "Evidence follow-through only; not win rate, P&L or trade advice.",
    }


def attach_evidence_follow_through(snapshot: dict[str, object]) -> None:
    coins = snapshot.get("coins", [])
    if not isinstance(coins, list):
        return
    for coin in coins:
        if not isinstance(coin, dict):
            continue
        coin["evidence_follow_through"] = build_evidence_follow_through(
            coin.get("recent_scan_history", [])
        )
