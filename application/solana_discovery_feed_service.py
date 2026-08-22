"""Read-only adapter for the Phase 0 Solana Discovery collector output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from application.solana_discovery_qualification import qualify_discovery_candidates


DEFAULT_OUTPUT_DIR = Path("output/research/solana-discovery-phase0-seven-day")


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _integer(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _freshness_label(value: Any, *, now: datetime) -> tuple[str, bool]:
    if not isinstance(value, str) or not value.strip():
        return "Unknown", False
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age_minutes = max(0, int((now - observed.astimezone(timezone.utc)).total_seconds() / 60))
    except ValueError:
        return "Unknown", False
    if age_minutes < 2:
        return "Just now", True
    if age_minutes < 60:
        return f"{age_minutes} min ago", True
    return f"{age_minutes // 60} hr ago", age_minutes <= 360


def load_solana_discovery_feed(
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a conservative public read model without exposing raw candidates."""
    directory = Path(output_dir)
    current_time = now or datetime.now(timezone.utc)
    disconnected = {
        "connected": False,
        "fresh": False,
        "collector_status": "Unavailable",
        "tokens_observed": None,
        "pair_resolved": None,
        "pair_ready_percent": None,
        "qualified_candidates": None,
        "updated_label": "Not connected",
        "message": "Collector output is not available yet.",
    }
    try:
        state = _read_object(directory / "state.json")
        status = _read_object(directory / "status.json")
    except (OSError, json.JSONDecodeError, ValueError):
        return disconnected

    if not isinstance(state.get("candidates"), dict) or not isinstance(status.get("metrics"), dict):
        return {**disconnected, "message": "Collector output schema is not ready for public use."}

    metrics = status["metrics"]
    generated_at = status.get("generated_at")
    updated_label, fresh = _freshness_label(generated_at, now=current_time)
    collector_status = str(status.get("collector_status") or "Unknown").strip().title()
    qualified = qualify_discovery_candidates(state["candidates"], now=current_time) if fresh else []
    return {
        "connected": True,
        "fresh": fresh,
        "collector_status": collector_status,
        "tokens_observed": len(state["candidates"]),
        "pair_resolved": _integer(metrics.get("pair_resolved")),
        "pair_ready_percent": metrics.get("pair_ready_percent"),
        "qualified_candidates": len(qualified),
        "candidates": qualified,
        "updated_label": updated_label,
        "message": (
            "Qualified candidates are based on verified Solana pool identity, observable liquidity "
            "and recent trading activity. Token security is not independently verified."
            if qualified else
            "Collector telemetry is connected. No observed token currently passes the "
            "required identity, liquidity, activity and freshness checks."
        ),
    }
