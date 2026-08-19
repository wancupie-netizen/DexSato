"""Bounded recent-scan history embedded in the latest snapshot."""

from __future__ import annotations


MAX_SCAN_HISTORY = 12


def _number(value: object) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def build_scan_history_point(
    coin: dict[str, object], *, recorded_at: str,
) -> dict[str, object]:
    evidence = coin.get("technical_evidence", {})
    evidence = evidence if isinstance(evidence, dict) else {}
    outlook = evidence.get("outlook", {})
    metrics = evidence.get("metrics", {})
    outlook = outlook if isinstance(outlook, dict) else {}
    metrics = metrics if isinstance(metrics, dict) else {}
    rsi = metrics.get("rsi_14", {})
    volume = metrics.get("relative_volume_20", {})
    return {
        "recorded_at": recorded_at,
        "decision": str(coin.get("decision", "UNKNOWN")).upper(),
        "confidence": str(coin.get("confidence", "UNKNOWN")).upper(),
        "technical_bias": str(outlook.get("bias", "UNKNOWN")).upper(),
        "rsi_14": _number(rsi.get("value") if isinstance(rsi, dict) else None),
        "relative_volume": _number(
            volume.get("value") if isinstance(volume, dict) else None
        ),
        "price": _number(coin.get("price")),
    }


def attach_recent_scan_history(
    current_snapshot: dict[str, object], previous_snapshot: dict[str, object] | None,
) -> None:
    """Carry forward a bounded history and append the current observation."""
    recorded_at = str(current_snapshot.get("generated_at", ""))
    previous_by_token = {}
    if isinstance(previous_snapshot, dict):
        previous_coins = previous_snapshot.get("coins", [])
        if isinstance(previous_coins, list):
            previous_by_token = {
                str(coin.get("token", "")).upper(): coin
                for coin in previous_coins if isinstance(coin, dict)
            }
    coins = current_snapshot.get("coins", [])
    if not isinstance(coins, list):
        return
    for coin in coins:
        if not isinstance(coin, dict):
            continue
        previous = previous_by_token.get(str(coin.get("token", "")).upper(), {})
        carried = previous.get("recent_scan_history", []) if isinstance(previous, dict) else []
        history = [dict(point) for point in carried if isinstance(point, dict)] \
            if isinstance(carried, list) else []
        point = build_scan_history_point(coin, recorded_at=recorded_at)
        history = [item for item in history if item.get("recorded_at") != recorded_at]
        history.append(point)
        coin["recent_scan_history"] = history[-MAX_SCAN_HISTORY:]
