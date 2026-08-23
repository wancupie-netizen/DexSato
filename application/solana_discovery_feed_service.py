"""Read-only adapter for the Phase 0 Solana Discovery collector output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from application.solana_discovery_qualification import qualify_discovery_candidates


DEFAULT_OUTPUT_DIR = Path("output/research/solana-discovery-phase0-seven-day")
DISCOVERY_HISTORY_FILE = "discovery_feed_history.json"
MAX_DISCOVERY_HISTORY = 100


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



def _history_key(candidate: dict[str, Any]) -> tuple[str, str]:
    return (
        str(candidate.get("token_address") or "").strip(),
        str(candidate.get("pair_address") or "").strip(),
    )


def _load_history(directory: Path) -> list[dict[str, Any]]:
    path = directory / DISCOVERY_HISTORY_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _write_history(directory: Path, candidates: list[dict[str, Any]]) -> None:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / DISCOVERY_HISTORY_FILE
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"candidates": candidates}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        return


def _merge_history(
    existing: list[dict[str, Any]],
    qualified: list[dict[str, Any]],
    *,
    qualified_at: str,
) -> list[dict[str, Any]]:
    current_tokens = {
        str(item.get("token_address") or "").strip()
        for item in qualified
        if isinstance(item, dict)
    }
    current_pairs = {
        str(item.get("pair_address") or "").strip()
        for item in qualified
        if isinstance(item, dict)
    }

    combined: list[dict[str, Any]] = []
    for item in qualified:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        record["currently_qualified"] = True
        record["last_qualified_at"] = qualified_at
        combined.append(record)

    for item in existing:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        token, pair = _history_key(record)
        if not token or not pair or token in current_tokens or pair in current_pairs:
            continue
        record["currently_qualified"] = False
        combined.append(record)

    combined.sort(
        key=lambda item: str(item.get("last_qualified_at") or item.get("last_seen_at") or ""),
        reverse=True,
    )

    result: list[dict[str, Any]] = []
    seen_tokens: set[str] = set()
    seen_pairs: set[str] = set()
    for item in combined:
        token, pair = _history_key(item)
        if not token or not pair or token in seen_tokens or pair in seen_pairs:
            continue
        seen_tokens.add(token)
        seen_pairs.add(pair)
        result.append(item)
        if len(result) >= MAX_DISCOVERY_HISTORY:
            break
    return result

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
    existing_history = _load_history(directory)
    qualified_at = (
        str(generated_at).strip()
        if isinstance(generated_at, str) and generated_at.strip()
        else current_time.isoformat()
    )
    history = _merge_history(
        existing_history,
        qualified,
        qualified_at=qualified_at,
    )
    if qualified:
        _write_history(directory, history)
    return {
        "connected": True,
        "fresh": fresh,
        "collector_status": collector_status,
        "tokens_observed": len(state["candidates"]),
        "pair_resolved": _integer(metrics.get("pair_resolved")),
        "pair_ready_percent": metrics.get("pair_ready_percent"),
        "qualified_candidates": len(qualified),
        "candidates": history,
        "updated_label": updated_label,
        "message": (
            "Qualified Now reflects the current scan. Discovery Feed keeps previously qualified "
            "tokens for review; historical inclusion does not mean a token still qualifies now."
            if qualified else
            "Collector telemetry is connected. No observed token currently passes the "
            "required identity, liquidity, activity and freshness checks."
        ),
    }
