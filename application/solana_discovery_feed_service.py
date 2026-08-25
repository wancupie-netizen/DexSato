"""Read-only adapter for the Phase 0 Solana Discovery collector output."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from application.solana_discovery_qualification import qualify_discovery_candidates


DEFAULT_OUTPUT_DIR = Path("output/research/solana-discovery-phase0-seven-day")
DISCOVERY_HISTORY_FILE = "discovery_feed_history.json"  # legacy v3.6 migration source
DISCOVERY_ARCHIVE_DB = "discovery_archive.sqlite3"
DISCOVERY_FEED_LIMIT = 100


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


def _load_legacy_history(directory: Path) -> list[dict[str, Any]]:
    """Read the v3.6 JSON file only as an idempotent migration source."""
    path = directory / DISCOVERY_HISTORY_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _archive_connection(directory: Path) -> sqlite3.Connection:
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(directory / DISCOVERY_ARCHIVE_DB)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS discoveries (
            token_address TEXT PRIMARY KEY,
            pair_address TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            first_qualified_at TEXT NOT NULL,
            last_qualified_at TEXT NOT NULL,
            last_seen_at TEXT,
            currently_qualified INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_discoveries_rank
        ON discoveries(currently_qualified DESC, last_qualified_at DESC)
        """
    )
    return connection


def _candidate_timestamp(candidate: dict[str, Any], fallback: str) -> str:
    value = str(
        candidate.get("last_qualified_at")
        or candidate.get("last_seen_at")
        or fallback
        or ""
    ).strip()
    return value or fallback


def _migrate_legacy_history(
    connection: sqlite3.Connection,
    directory: Path,
    *,
    fallback_at: str,
) -> None:
    """Import every v3.6 JSON history row without deleting or truncating it."""
    for item in _load_legacy_history(directory):
        token, pair = _history_key(item)
        if not token or not pair:
            continue
        qualified_at = _candidate_timestamp(item, fallback_at)
        first_at = str(item.get("first_qualified_at") or qualified_at).strip() or qualified_at
        last_seen_at = str(item.get("last_seen_at") or "").strip() or None
        connection.execute(
            """
            INSERT OR IGNORE INTO discoveries (
                token_address, pair_address, payload_json, first_qualified_at,
                last_qualified_at, last_seen_at, currently_qualified
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                pair,
                json.dumps(dict(item), ensure_ascii=False),
                first_at,
                qualified_at,
                last_seen_at,
                1 if item.get("currently_qualified") is True else 0,
            ),
        )


def _update_archive(
    directory: Path,
    qualified: list[dict[str, Any]],
    *,
    qualified_at: str,
) -> tuple[list[dict[str, Any]], int]:
    """Persist all discoveries; limit only the public front feed to 100 rows."""
    with _archive_connection(directory) as connection:
        _migrate_legacy_history(connection, directory, fallback_at=qualified_at)
        connection.execute("UPDATE discoveries SET currently_qualified = 0")

        for item in qualified:
            if not isinstance(item, dict):
                continue
            token, pair = _history_key(item)
            if not token or not pair:
                continue

            payload = dict(item)
            payload["currently_qualified"] = True
            payload["last_qualified_at"] = qualified_at
            last_seen_at = str(item.get("last_seen_at") or "").strip() or None

            connection.execute(
                """
                INSERT INTO discoveries (
                    token_address, pair_address, payload_json, first_qualified_at,
                    last_qualified_at, last_seen_at, currently_qualified
                ) VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(token_address) DO UPDATE SET
                    pair_address = excluded.pair_address,
                    payload_json = excluded.payload_json,
                    last_qualified_at = excluded.last_qualified_at,
                    last_seen_at = excluded.last_seen_at,
                    currently_qualified = 1
                """,
                (
                    token,
                    pair,
                    json.dumps(payload, ensure_ascii=False),
                    qualified_at,
                    qualified_at,
                    last_seen_at,
                ),
            )

        archive_total = int(
            connection.execute("SELECT COUNT(*) FROM discoveries").fetchone()[0]
        )
        rows = connection.execute(
            """
            SELECT payload_json, first_qualified_at, last_qualified_at,
                   last_seen_at, currently_qualified
            FROM discoveries
            ORDER BY currently_qualified DESC,
                     last_qualified_at DESC,
                     COALESCE(last_seen_at, '') DESC,
                     token_address ASC
            LIMIT ?
            """,
            (DISCOVERY_FEED_LIMIT,),
        ).fetchall()

    feed: list[dict[str, Any]] = []
    for payload_json, first_at, last_at, last_seen_at, current_flag in rows:
        try:
            item = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(item, dict):
            continue
        record = dict(item)
        record["first_qualified_at"] = first_at
        record["last_qualified_at"] = last_at
        if last_seen_at:
            record["last_seen_at"] = last_seen_at
        record["currently_qualified"] = bool(current_flag)
        feed.append(record)

    return feed, archive_total

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
    qualified_at = (
        str(generated_at).strip()
        if isinstance(generated_at, str) and generated_at.strip()
        else current_time.isoformat()
    )
    archive_feed, archive_total = _update_archive(
        directory,
        qualified,
        qualified_at=qualified_at,
    )
    return {
        "connected": True,
        "fresh": fresh,
        "collector_status": collector_status,
        "tokens_observed": len(state["candidates"]),
        "pair_resolved": _integer(metrics.get("pair_resolved")),
        "pair_ready_percent": metrics.get("pair_ready_percent"),
        "qualified_candidates": len(qualified),
        "candidates": archive_feed,
        "archive_total": archive_total,
        "feed_limit": DISCOVERY_FEED_LIMIT,
        "updated_label": updated_label,
        "message": (
            "Qualified Now reflects the current scan. Discovery Feed keeps previously qualified "
            "tokens for review; historical inclusion does not mean a token still qualifies now."
            if qualified else
            "Collector telemetry is connected. No observed token currently passes the "
            "required identity, liquidity, activity and freshness checks. Previously qualified "
            "discoveries remain in the persistent archive."
        ),
    }
