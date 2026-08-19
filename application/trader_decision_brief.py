"""Deterministic trader-facing synthesis of stored DexSato evidence."""

from __future__ import annotations


def _conditions(outlook: dict[str, object], key: str, statuses: set[str]) -> list[dict[str, str]]:
    rows = []
    values = outlook.get(key, [])
    if not isinstance(values, list):
        return rows
    for value in values:
        if not isinstance(value, dict) or str(value.get("status", "")).upper() not in statuses:
            continue
        rows.append({
            "label": str(value.get("label", "Condition")),
            "actual": str(value.get("actual", "Not available")),
            "requirement": str(value.get("requirement", "Not available")),
            "status": str(value.get("status", "UNKNOWN")).upper(),
        })
    return rows[:3]


def build_trader_decision_brief(
    *, decision: object, confidence: object,
    technical_evidence: object, fundamental_context: object,
    market_catalysts: object,
) -> dict[str, object]:
    """Explain evidence alignment without generating signals or trade advice."""
    technical = technical_evidence if isinstance(technical_evidence, dict) else {}
    outlook = technical.get("outlook", {})
    outlook = outlook if isinstance(outlook, dict) else {}
    bias = str(outlook.get("bias", "MIXED")).upper()
    decision_label = str(decision or "UNAVAILABLE").upper()
    confidence_label = str(confidence or "UNAVAILABLE").upper()

    if bias == "BULLISH_DEVELOPING":
        state = "UPSIDE_EVIDENCE_DEVELOPING"
        headline = "Upside 4H evidence is developing, but is not yet a confirmed setup"
    elif bias == "BEARISH_DEVELOPING":
        state = "DOWNSIDE_EVIDENCE_DEVELOPING"
        headline = "Downside 4H evidence is developing, but is not yet a confirmed setup"
    else:
        state = "NO_DIRECTIONAL_THESIS"
        headline = "No directional 4H thesis is confirmed"

    pending = _conditions(outlook, "confirmation", {"PENDING"})
    invalidation = _conditions(outlook, "invalidation", {"CLEAR", "TRIGGERED"})
    if bias == "MIXED":
        action = (
            "Wait for price structure, momentum and volume to align before treating "
            "this market as a directional setup."
        )
    else:
        action = (
            "Treat the directional view as developing only. The pending conditions "
            "below must improve before the evidence becomes stronger."
        )

    context_notes = []
    fundamental = fundamental_context if isinstance(fundamental_context, dict) else {}
    if fundamental.get("status") == "AVAILABLE" and fundamental.get("headline"):
        context_notes.append({
            "type": "MACRO", "text": str(fundamental["headline"]),
            "relationship": "CONTEXTUAL",
        })
    catalysts = market_catalysts if isinstance(market_catalysts, dict) else {}
    catalyst_rows = catalysts.get("catalysts", [])
    if isinstance(catalyst_rows, list) and catalyst_rows and isinstance(catalyst_rows[0], dict):
        context_notes.append({
            "type": "OFFICIAL_CATALYST",
            "text": str(catalyst_rows[0].get("title", "Official announcement available")),
            "relationship": "CONTEXTUAL",
        })

    return {
        "status": "AVAILABLE" if outlook else "INSUFFICIENT_EVIDENCE",
        "state": state,
        "headline": headline,
        "summary": (
            f"DexSato currently marks this market {decision_label} with "
            f"{confidence_label} confidence. Technical evidence remains "
            f"{bias.replace('_', ' ').lower()}."
        ),
        "next_action": action,
        "pending_confirmation": pending,
        "invalidation": invalidation,
        "context_notes": context_notes,
        "policy": "Evidence synthesis only; not a trade instruction.",
    }
