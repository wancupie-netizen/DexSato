"""Freshness and safe-degradation policy for displayed market evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _utc(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _timed_check(
    *, label: str, timestamp: object, now: datetime,
    fresh_for: timedelta, stale_after: timedelta, source_status: str = "AVAILABLE",
) -> dict[str, object]:
    status = str(source_status or "UNAVAILABLE").upper()
    if status not in {"AVAILABLE", "NO_MATCH", "NO_RECENT_CATALYSTS"}:
        return {
            "label": label, "state": "UNAVAILABLE", "observed_at": None,
            "age_minutes": None,
        }
    observed_at = _utc(timestamp)
    if observed_at is None:
        return {
            "label": label, "state": "UNAVAILABLE", "observed_at": None,
            "age_minutes": None,
        }
    age = max(timedelta(0), now - observed_at)
    state = "FRESH" if age <= fresh_for else "AGING" if age <= stale_after else "STALE"
    return {
        "label": label,
        "state": state,
        "observed_at": observed_at.isoformat(),
        "age_minutes": round(age.total_seconds() / 60),
    }


def build_evidence_health(
    coin: dict[str, object], *, evaluated_at: datetime,
) -> dict[str, object]:
    """Classify source freshness without modifying the engine decision."""
    if evaluated_at.tzinfo is None:
        raise ValueError("Evidence-health timestamp must be timezone-aware.")
    now = evaluated_at.astimezone(timezone.utc)
    technical = coin.get("technical_evidence", {})
    fundamental = coin.get("fundamental_context", {})
    catalysts = coin.get("market_catalysts", {})
    if not isinstance(technical, dict):
        technical = {}
    if not isinstance(fundamental, dict):
        fundamental = {}
    if not isinstance(catalysts, dict):
        catalysts = {}

    checks = {
        "market_snapshot": _timed_check(
            label="Market snapshot", timestamp=coin.get("scanned_at"), now=now,
            fresh_for=timedelta(hours=8), stale_after=timedelta(hours=14),
            source_status="AVAILABLE" if coin.get("available") is True else "UNAVAILABLE",
        ),
        "technical_4h": _timed_check(
            label="Technical evidence · 4H",
            timestamp=technical.get("candle_closed_at"), now=now,
            fresh_for=timedelta(hours=8), stale_after=timedelta(hours=12),
            source_status=str(technical.get("status") or coin.get("technical_evidence_status") or "UNAVAILABLE"),
        ),
        "trading_venues": _timed_check(
            label="Trading venues", timestamp=coin.get("scanned_at"), now=now,
            fresh_for=timedelta(hours=8), stale_after=timedelta(hours=14),
            source_status=str(coin.get("trading_venues_status") or "UNAVAILABLE"),
        ),
        "fundamental_context": _timed_check(
            label="Official macro context", timestamp=fundamental.get("collected_at"), now=now,
            fresh_for=timedelta(days=35), stale_after=timedelta(days=60),
            source_status=str(fundamental.get("status") or coin.get("fundamental_context_status") or "UNAVAILABLE"),
        ),
        "market_catalysts": _timed_check(
            label="Official market catalysts", timestamp=catalysts.get("collected_at"), now=now,
            fresh_for=timedelta(hours=24), stale_after=timedelta(hours=72),
            source_status=str(catalysts.get("status") or coin.get("market_catalysts_status") or "UNAVAILABLE"),
        ),
    }
    asset_class = str(coin.get("asset_class") or "crypto").lower()
    required = ["market_snapshot"]
    if asset_class == "crypto":
        required.append("technical_4h")
    required_states = [str(checks[key]["state"]) for key in required]
    all_states = [str(check["state"]) for check in checks.values()]

    if "STALE" in required_states:
        overall = "STALE"
        summary = "A required evidence source is stale. Treat the displayed decision as historical context until a fresh scan completes."
    elif "UNAVAILABLE" in required_states:
        overall = "PARTIAL"
        summary = "A required evidence source is unavailable. The decision remains visible, but its supporting context is incomplete."
    elif "AGING" in required_states:
        overall = "AGING"
        summary = "Required evidence is approaching its freshness limit. Confirm the next completed scan before relying on it."
    elif any(state in {"UNAVAILABLE", "STALE"} for state in all_states):
        overall = "PARTIAL"
        summary = "Core evidence is fresh, but one or more contextual sources are unavailable or stale."
    elif "AGING" in all_states:
        overall = "AGING"
        summary = "Core evidence is fresh, while at least one contextual source is aging."
    else:
        overall = "FRESH"
        summary = "Required market and technical evidence is within the defined freshness policy."

    return {
        "status": overall,
        "evaluated_at": now.isoformat(),
        "summary": summary,
        "technical_usable": checks["technical_4h"]["state"] in {"FRESH", "AGING"},
        "checks": checks,
        "policy": {
            "market_snapshot": "fresh ≤8h; stale >14h",
            "technical_4h": "fresh ≤8h; stale >12h",
            "fundamental_context": "fresh ≤35d; stale >60d",
            "market_catalysts": "fresh ≤24h; stale >72h",
        },
    }


def attach_evidence_health(snapshot: dict[str, object]) -> None:
    """Attach evidence-health metadata to every serialized market."""
    evaluated_at = _utc(snapshot.get("generated_at"))
    if evaluated_at is None:
        raise ValueError("Snapshot generated_at must be timezone-aware.")
    coins = snapshot.get("coins", [])
    if not isinstance(coins, list):
        return
    for coin in coins:
        if isinstance(coin, dict):
            coin["evidence_health"] = build_evidence_health(
                coin, evaluated_at=evaluated_at,
            )
