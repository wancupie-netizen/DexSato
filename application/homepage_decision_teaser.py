"""Deterministic, evidence-led summaries for homepage market cards."""

from __future__ import annotations


def _label(value: object) -> str:
    return str(value or "").replace("_", " ").title()


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _technical_evidence(coin: dict[str, object]) -> tuple[list[dict[str, str]], dict[str, object]]:
    technical = coin.get("technical_evidence", {})
    if not isinstance(technical, dict) or technical.get("status") != "AVAILABLE":
        return [], {}
    metrics = technical.get("metrics", {})
    outlook = technical.get("outlook", {})
    if not isinstance(metrics, dict):
        metrics = {}
    if not isinstance(outlook, dict):
        outlook = {}

    items: list[dict[str, str]] = []
    bias = _label(outlook.get("bias"))
    if bias:
        items.append({"label": "4H bias", "value": bias, "detail": ""})

    rsi = metrics.get("rsi_14", {})
    if isinstance(rsi, dict) and _number(rsi.get("value")) is not None:
        value = _number(rsi.get("value"))
        previous = _number(rsi.get("previous"))
        direction = _label(rsi.get("direction"))
        detail = direction
        if previous is not None:
            detail = f"{direction} · previous {previous:.2f}" if direction else f"Previous {previous:.2f}"
        items.append({"label": "RSI(14)", "value": f"{value:.2f}", "detail": detail})

    volume = metrics.get("relative_volume_20", {})
    if isinstance(volume, dict) and _number(volume.get("value")) is not None:
        value = _number(volume.get("value"))
        participation = "Expanding participation" if value >= 1.5 else "Normal participation" if value >= 1 else "Light participation"
        items.append({"label": "Relative volume", "value": f"{value:.2f}×", "detail": participation})
    return items[:3], outlook


def _pending_confirmation(outlook: dict[str, object]) -> dict[str, str] | None:
    conditions = outlook.get("confirmation", [])
    if not isinstance(conditions, list):
        return None
    for condition in conditions:
        if isinstance(condition, dict) and str(condition.get("status", "")).upper() == "PENDING":
            return {
                "label": str(condition.get("label") or "Confirmation pending"),
                "actual": str(condition.get("actual") or "Current value unavailable"),
                "requirement": str(condition.get("requirement") or "Await the next completed scan"),
            }
    return None


def build_homepage_decision_teaser(coin: dict[str, object]) -> dict[str, object]:
    """Build a compact homepage reason-to-click without AI-generated prose."""
    evidence, outlook = _technical_evidence(coin)
    decision = str(coin.get("decision") or "UNAVAILABLE").upper()
    confidence = str(coin.get("confidence") or "UNKNOWN").upper()
    change = coin.get("change_since_previous", {})
    follow = coin.get("evidence_follow_through", {})
    brief = coin.get("trader_decision_brief", {})

    headline = "Review the current market evidence"
    summary = f"DexSato marks this market {decision} with {confidence} confidence."
    context = "CURRENT SNAPSHOT"

    if isinstance(change, dict) and change.get("status") == "CHANGED":
        headline = str(change.get("headline") or "Material evidence changed since the previous scan")
        summary = "Open the evidence trail to see what changed and which condition matters next."
        context = "CHANGED SINCE PREVIOUS SCAN"
    elif isinstance(follow, dict) and follow.get("status") == "AVAILABLE" and follow.get("evaluations"):
        evaluation = follow["evaluations"][0]
        if isinstance(evaluation, dict):
            result = _label(evaluation.get("result")) or "Available"
            horizon = str(evaluation.get("horizon") or "4H")
            headline = f"{horizon} evidence follow-through is {result.lower()}"
            summary = str(evaluation.get("summary") or "Review how price behaved after the recorded bias.")
            context = "AFTER THE EVIDENCE WAS RECORDED"
    elif isinstance(change, dict) and change.get("status") == "UNCHANGED":
        headline = str(change.get("headline") or "No material evidence change since the previous scan")
        summary = "The decision, confidence and technical state remain stable; review the pending condition before acting."
        context = "SINCE PREVIOUS SCAN"
    elif isinstance(brief, dict) and brief.get("status") == "AVAILABLE":
        headline = str(brief.get("headline") or headline)
        summary = str(brief.get("summary") or summary)
        context = "EVIDENCE-LED SYNTHESIS"
    elif outlook:
        bias = str(outlook.get("bias") or "MIXED").upper()
        headline = {
            "BULLISH_DEVELOPING": "Upside 4H evidence is developing",
            "BEARISH_DEVELOPING": "Downside 4H evidence is developing",
            "MIXED": "No directional 4H thesis is confirmed",
        }.get(bias, "Review the current 4H evidence")
        summary = str(outlook.get("summary") or summary)
        context = "TECHNICAL EVIDENCE"

    pending = _pending_confirmation(outlook)
    if pending is None:
        pending = {
            "label": "Await the next material evidence change",
            "actual": "No pending technical trigger recorded",
            "requirement": "Review again after the next completed scan",
        }

    return {
        "evidence": evidence,
        "context": context,
        "headline": headline,
        "summary": summary,
        "next_confirmation": pending,
    }
