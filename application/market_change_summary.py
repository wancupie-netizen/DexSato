"""Deterministic comparison between consecutive stored market snapshots."""

from __future__ import annotations


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _technical(coin: dict[str, object]) -> tuple[str, float | None, float | None]:
    evidence = coin.get("technical_evidence", {})
    if not isinstance(evidence, dict):
        return "UNKNOWN", None, None
    outlook = evidence.get("outlook", {})
    metrics = evidence.get("metrics", {})
    outlook = outlook if isinstance(outlook, dict) else {}
    metrics = metrics if isinstance(metrics, dict) else {}
    rsi = metrics.get("rsi_14", {})
    volume = metrics.get("relative_volume_20", {})
    return (
        str(outlook.get("bias", "UNKNOWN")).upper(),
        _number(rsi.get("value") if isinstance(rsi, dict) else None),
        _number(volume.get("value") if isinstance(volume, dict) else None),
    )


def build_market_change_summary(
    current: dict[str, object], previous: dict[str, object] | None,
) -> dict[str, object]:
    """Return auditable field deltas; never infer a new decision."""
    if previous is None:
        return {
            "status": "BASELINE", "headline": "Baseline snapshot established",
            "changes": [], "policy": "Comparison begins after the next completed scan.",
        }
    old_decision = str(previous.get("decision", "UNKNOWN")).upper()
    new_decision = str(current.get("decision", "UNKNOWN")).upper()
    old_confidence = str(previous.get("confidence", "UNKNOWN")).upper()
    new_confidence = str(current.get("confidence", "UNKNOWN")).upper()
    old_bias, old_rsi, old_volume = _technical(previous)
    new_bias, new_rsi, new_volume = _technical(current)
    changes = []

    def add(label: str, old: object, new: object, material: bool = True) -> None:
        if material and old != new:
            changes.append({"label": label, "previous": old, "current": new})

    add("DexSato decision", old_decision, new_decision)
    add("Decision confidence", old_confidence, new_confidence)
    add("4H technical bias", old_bias.replace("_", " ").title(),
        new_bias.replace("_", " ").title())
    if old_rsi is not None and new_rsi is not None:
        add("RSI(14)", f"{old_rsi:.2f}", f"{new_rsi:.2f}", abs(new_rsi - old_rsi) >= 1.0)
    if old_volume is not None and new_volume is not None:
        add("Relative volume", f"{old_volume:.2f}×", f"{new_volume:.2f}×",
            abs(new_volume - old_volume) >= 0.10)

    if old_decision != new_decision:
        headline = f"Decision changed from {old_decision} to {new_decision}"
    elif old_bias != new_bias:
        headline = (
            f"4H bias changed from {old_bias.replace('_', ' ').title()} to "
            f"{new_bias.replace('_', ' ').title()}"
        )
    elif changes:
        headline = "Market evidence changed since the previous scan"
    else:
        headline = "No material evidence change since the previous scan"
    return {
        "status": "CHANGED" if changes else "UNCHANGED",
        "headline": headline,
        "changes": changes,
        "policy": "Observed snapshot differences only; no causal inference.",
    }


def attach_market_change_summaries(
    current_snapshot: dict[str, object], previous_snapshot: dict[str, object] | None,
) -> None:
    """Attach a comparison to every current coin in place."""
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
        previous = previous_by_token.get(str(coin.get("token", "")).upper())
        coin["change_since_previous"] = build_market_change_summary(coin, previous)
