"""Audit how mature and internally consistent the displayed evidence is."""

from __future__ import annotations


BULLISH_ENGINE_SIGNALS = {
    "EARLY_MOMENTUM", "STRONG_MOMENTUM", "MOMENTUM_STRENGTHENED",
    "BREAKOUT_CONFIRMED", "BULLISH_BREAKOUT",
}
BEARISH_ENGINE_SIGNALS = {
    "DISTRIBUTION", "WEAK_MOMENTUM", "WEAK_BREAKOUT",
    "BEARISH_BREAKDOWN", "SELLING_PRESSURE",
}


def _direction_from_reasons(reasons: object) -> str:
    if not isinstance(reasons, list):
        return "NEUTRAL"
    normalized = {str(reason).upper() for reason in reasons}
    bullish = bool(normalized & BULLISH_ENGINE_SIGNALS)
    bearish = bool(normalized & BEARISH_ENGINE_SIGNALS)
    if bullish and not bearish:
        return "BULLISH"
    if bearish and not bullish:
        return "BEARISH"
    return "MIXED" if bullish and bearish else "NEUTRAL"


def _technical_direction(bias: str) -> str:
    if bias == "BULLISH_DEVELOPING":
        return "BULLISH"
    if bias == "BEARISH_DEVELOPING":
        return "BEARISH"
    return "MIXED"


def build_decision_readiness(coin: dict[str, object]) -> dict[str, object]:
    """Explain evidence maturity without treating it as trade readiness."""
    decision = str(coin.get("decision") or "UNAVAILABLE").upper()
    if decision == "REFERENCE" or str(coin.get("asset_class") or "").lower() == "commodity":
        return {
            "status": "CONTEXT_ONLY",
            "headline": "Reference context is not scored for decision readiness",
            "summary": "This market is displayed as contextual reference intelligence, not a directional DexSato decision.",
            "confirmation": {"met": 0, "pending": 0, "total": 0},
            "supporting_conditions": [], "pending_conditions": [], "conflicts": [],
            "policy": "DECISION_SUPPORT_ONLY_NOT_TRADE_READINESS",
        }

    health = coin.get("evidence_health", {})
    technical = coin.get("technical_evidence", {})
    if not isinstance(health, dict):
        health = {}
    if not isinstance(technical, dict):
        technical = {}
    outlook = technical.get("outlook", {})
    if not isinstance(outlook, dict):
        outlook = {}
    conditions = outlook.get("confirmation", [])
    if not isinstance(conditions, list):
        conditions = []

    met = [item for item in conditions if isinstance(item, dict) and str(item.get("status", "")).upper() == "MET"]
    pending = [item for item in conditions if isinstance(item, dict) and str(item.get("status", "")).upper() == "PENDING"]
    supporting = [str(item.get("label") or "Supporting condition") for item in met]
    still_needed = [str(item.get("label") or "Pending confirmation") for item in pending]
    health_status = str(health.get("status") or "UNKNOWN").upper()
    technical_usable = health.get("technical_usable") is not False
    bias = str(outlook.get("bias") or "MIXED").upper()
    engine_direction = _direction_from_reasons(coin.get("reasons", []))
    technical_direction = _technical_direction(bias)
    conflicts: list[str] = []
    if (
        engine_direction in {"BULLISH", "BEARISH"}
        and technical_direction in {"BULLISH", "BEARISH"}
        and engine_direction != technical_direction
    ):
        conflicts.append(
            f"Engine signals are {engine_direction.lower()} while 4H technical evidence is {technical_direction.lower()}."
        )

    if health_status == "STALE" or not technical_usable:
        status = "STALE"
        headline = "Fresh evidence is required before readiness can be assessed"
        summary = "At least one required evidence source exceeded its freshness limit. The stored decision remains visible as historical context."
    elif not outlook or technical.get("status") != "AVAILABLE":
        status = "LIMITED"
        headline = "Decision evidence is incomplete"
        summary = "The engine decision is available, but auditable 4H confirmation evidence has not been collected."
    elif conflicts:
        status = "CONFLICTED"
        headline = "Engine and technical direction do not align"
        summary = "Opposing directional evidence is present. Review the conflict and wait for alignment before treating the setup as mature."
    elif technical_direction in {"BULLISH", "BEARISH"} and len(met) >= 3:
        status = "WELL_SUPPORTED"
        headline = "Most defined technical conditions are confirmed"
        summary = f"{len(met)} of {len(conditions)} confirmation conditions are met. This strengthens the evidence case but is not a trade instruction."
    else:
        status = "DEVELOPING"
        headline = "The evidence case is still developing"
        summary = f"{len(met)} of {len(conditions)} confirmation conditions are met. Pending conditions must improve before the evidence is considered mature."

    return {
        "status": status,
        "headline": headline,
        "summary": summary,
        "engine_direction": engine_direction,
        "technical_direction": technical_direction,
        "confirmation": {"met": len(met), "pending": len(pending), "total": len(conditions)},
        "supporting_conditions": supporting,
        "pending_conditions": still_needed,
        "conflicts": conflicts,
        "policy": "DECISION_SUPPORT_ONLY_NOT_TRADE_READINESS",
    }


def attach_decision_readiness(snapshot: dict[str, object]) -> None:
    """Attach readiness audits after evidence-health classification."""
    coins = snapshot.get("coins", [])
    if not isinstance(coins, list):
        return
    for coin in coins:
        if isinstance(coin, dict):
            coin["decision_readiness"] = build_decision_readiness(coin)
