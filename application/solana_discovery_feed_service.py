"""Read-only adapter for the Phase 0 Solana Discovery collector output."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from application.solana_discovery_qualification import qualify_discovery_candidates
from application.discovery_storage import discovery_storage_dir


DEFAULT_OUTPUT_DIR = Path("output/research/solana-discovery-phase0-seven-day")
DISCOVERY_HISTORY_FILE = "discovery_feed_history.json"  # legacy v3.6 migration source
DISCOVERY_ARCHIVE_DB = "discovery_archive.sqlite3"
DISCOVERY_FEED_LIMIT = 100
TERMINAL_PAGE_SIZE = 25
TERMINAL_VIEWS = {"qualified", "recent", "archive"}

_ENGINE_FEED_LOCK = threading.Lock()
_ENGINE_FEED_GENERATED_AT: str | None = None


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


def _archive_read_connection(directory: Path) -> sqlite3.Connection:
    """Open the archive strictly read-only; never create schema from a request path."""
    database = directory / DISCOVERY_ARCHIVE_DB
    if not database.is_file():
        raise FileNotFoundError(database)
    return sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)


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
    diagnostics: dict[str, dict[str, Any]] | None = None,
    default_diagnostic: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Persist all discoveries; limit only the public front feed to 100 rows."""
    with _archive_connection(directory) as connection:
        _migrate_legacy_history(connection, directory, fallback_at=qualified_at)
        connection.execute("UPDATE discoveries SET currently_qualified = 0")

        existing_rows = connection.execute("SELECT token_address, payload_json FROM discoveries").fetchall()
        for existing_token, payload_json in existing_rows:
            try:
                existing_payload = json.loads(payload_json)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(existing_payload, dict):
                continue
            assessment = (diagnostics or {}).get(str(existing_token)) or default_diagnostic or {
                "evaluated": False,
                "qualified": False,
                "code": "not_observed_current_scan",
                "title": "Not observed in current scan",
                "message": "This archived token was not present in the current collector candidate set.",
                "scan_at": qualified_at,
            }
            existing_payload["current_qualification"] = dict(assessment)
            connection.execute(
                "UPDATE discoveries SET payload_json = ? WHERE token_address = ?",
                (json.dumps(existing_payload, ensure_ascii=False), existing_token),
            )

        for item in qualified:
            if not isinstance(item, dict):
                continue
            token, pair = _history_key(item)
            if not token or not pair:
                continue

            payload = dict(item)
            payload["currently_qualified"] = True
            payload["last_qualified_at"] = qualified_at
            payload["current_qualification"] = (diagnostics or {}).get(token) or {
                "evaluated": True,
                "qualified": True,
                "code": "qualified",
                "title": "Qualified now",
                "message": "Current identity, exact-pool, liquidity and 24h activity checks passed.",
            }
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


def _archive_record(row: tuple[Any, ...]) -> dict[str, Any] | None:
    payload_json, first_at, last_at, last_seen_at, current_flag = row
    try:
        item = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(item, dict):
        return None
    record = dict(item)
    record["first_qualified_at"] = first_at
    record["last_qualified_at"] = last_at
    if last_seen_at:
        record["last_seen_at"] = last_seen_at
    record["currently_qualified"] = bool(current_flag)
    return record



def _stale_qualification_diagnostic(generated_at: Any) -> dict[str, Any]:
    return {
        "evaluated": False,
        "qualified": False,
        "code": "collector_not_fresh",
        "title": "Collector data is not fresh",
        "message": "Qualification was not evaluated because the collector snapshot is stale.",
        "scan_at": str(generated_at or "").strip() or None,
    }


def _read_archive_front_feed(
    directory: Path,
    *,
    fresh: bool,
    generated_at: Any,
) -> tuple[list[dict[str, Any]], int, int]:
    """Read front-feed rows without creating, migrating, qualifying or mutating the archive."""
    database = directory / DISCOVERY_ARCHIVE_DB
    if not database.is_file():
        return [], 0, 0

    try:
        with _archive_read_connection(directory) as connection:
            archive_total = int(
                connection.execute("SELECT COUNT(*) FROM discoveries").fetchone()[0]
            )
            qualified_total = int(
                connection.execute(
                    "SELECT COUNT(*) FROM discoveries WHERE currently_qualified = 1"
                ).fetchone()[0]
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
    except (FileNotFoundError, sqlite3.Error):
        return [], 0, 0

    stale_diagnostic = _stale_qualification_diagnostic(generated_at)
    feed: list[dict[str, Any]] = []
    for row in rows:
        record = _archive_record(row)
        if record is None:
            continue
        if not fresh:
            record["currently_qualified"] = False
            record["current_qualification"] = dict(stale_diagnostic)
        feed.append(record)

    return feed, archive_total, qualified_total if fresh else 0


def load_solana_discovery_record(
    token_address: str,
    output_dir: Path | str | None = None,
) -> dict[str, Any] | None:
    """Load one persistent observation by exact mint without front-page limits."""
    token = str(token_address or "").strip()
    if not token or len(token) > 80:
        return None
    directory = Path(output_dir) if output_dir is not None else discovery_storage_dir(DEFAULT_OUTPUT_DIR)
    if not (directory / DISCOVERY_ARCHIVE_DB).exists():
        return None
    with _archive_read_connection(directory) as connection:
        row = connection.execute(
            """
            SELECT payload_json, first_qualified_at, last_qualified_at,
                   last_seen_at, currently_qualified
            FROM discoveries WHERE token_address = ?
            """,
            (token,),
        ).fetchone()
    return _archive_record(row) if row is not None else None


def _terminal_archive_view(
    directory: Path,
    *,
    view: str,
    page: int,
    page_size: int,
    now: datetime,
    query: str = "",
    fresh: bool = True,
    generated_at: Any = None,
) -> dict[str, Any]:
    selected_view = view if view in TERMINAL_VIEWS else "qualified"
    safe_size = min(100, max(1, _integer(page_size) or TERMINAL_PAGE_SIZE))
    requested_page = max(1, _integer(page) or 1)
    recent_cutoff = (now.astimezone(timezone.utc) - timedelta(hours=24)).isoformat()
    search_query = str(query or "").strip()[:120]
    qualified_where = "currently_qualified = 1" if fresh else "0 = 1"
    clauses = {
        "qualified": (qualified_where, ()),
        "recent": ("datetime(first_qualified_at) >= datetime(?)", (recent_cutoff,)),
        "archive": ("1 = 1", ()),
    }
    where, parameters = clauses[selected_view]
    search_sql = ""
    search_parameters: tuple[Any, ...] = ()
    if search_query:
        escaped_query = search_query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped_query}%"
        search_sql = """ AND (
            LOWER(token_address) LIKE ? ESCAPE '\\' OR
            LOWER(pair_address) LIKE ? ESCAPE '\\' OR
            LOWER(COALESCE(json_extract(payload_json, '$.symbol'), '')) LIKE ? ESCAPE '\\' OR
            LOWER(COALESCE(json_extract(payload_json, '$.name'), '')) LIKE ? ESCAPE '\\' OR
            LOWER(COALESCE(json_extract(payload_json, '$.dex_id'), '')) LIKE ? ESCAPE '\\'
        )"""
        search_parameters = (pattern,) * 5
    orders = {
        "qualified": "COALESCE(last_seen_at, '') DESC, last_qualified_at DESC, token_address ASC",
        "recent": "first_qualified_at DESC, token_address ASC",
        "archive": "last_qualified_at DESC, COALESCE(last_seen_at, '') DESC, token_address ASC",
    }

    if not (directory / DISCOVERY_ARCHIVE_DB).is_file():
        return {
            "candidates": [], "view": selected_view, "page": 1, "page_size": safe_size,
            "page_count": 1, "view_total": 0, "search_query": search_query,
            "search_counts": {key: 0 for key in TERMINAL_VIEWS},
            "qualified_total": 0, "recent_total": 0, "archive_total": 0,
            "observed_volume_24h_usd": 0, "observed_txns_24h": 0, "observed_dex_ids": [],
        }

    with _archive_read_connection(directory) as connection:
        qualified_total = (
            int(connection.execute(
                "SELECT COUNT(*) FROM discoveries WHERE currently_qualified = 1"
            ).fetchone()[0])
            if fresh else 0
        )
        recent_total = int(connection.execute(
            "SELECT COUNT(*) FROM discoveries WHERE datetime(first_qualified_at) >= datetime(?)", (recent_cutoff,)
        ).fetchone()[0])
        archive_total = int(connection.execute("SELECT COUNT(*) FROM discoveries").fetchone()[0])
        filtered_counts = {}
        for key, (count_where, count_parameters) in clauses.items():
            filtered_counts[key] = int(connection.execute(
                f"SELECT COUNT(*) FROM discoveries WHERE {count_where}{search_sql}",
                (*count_parameters, *search_parameters),
            ).fetchone()[0])
        view_total = filtered_counts[selected_view]
        page_count = max(1, (view_total + safe_size - 1) // safe_size)
        current_page = min(requested_page, page_count)
        rows = connection.execute(
            f"""
            SELECT payload_json, first_qualified_at, last_qualified_at,
                   last_seen_at, currently_qualified
            FROM discoveries WHERE {where}{search_sql}
            ORDER BY {orders[selected_view]}
            LIMIT ? OFFSET ?
            """,
            (*parameters, *search_parameters, safe_size, (current_page - 1) * safe_size),
        ).fetchall()
        current_rows = (
            connection.execute(
                "SELECT payload_json FROM discoveries WHERE currently_qualified = 1"
            ).fetchall()
            if fresh else []
        )

    candidates = [record for row in rows if (record := _archive_record(row)) is not None]
    if not fresh:
        stale_diagnostic = _stale_qualification_diagnostic(generated_at)
        for record in candidates:
            record["currently_qualified"] = False
            record["current_qualification"] = dict(stale_diagnostic)
    current_payloads: list[dict[str, Any]] = []
    for (payload_json,) in current_rows:
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            current_payloads.append(payload)

    def complete_sum(field: str) -> float | int | None:
        if qualified_total == 0:
            return 0
        values: list[float] = []
        for payload in current_payloads:
            try:
                value = float(payload.get(field))
            except (TypeError, ValueError):
                return None
            if value < 0:
                return None
            values.append(value)
        if not values:
            return None
        total = sum(values)
        return int(total) if field == "txns_24h" else total

    dex_ids = sorted({
        str(payload.get("dex_id") or "").strip()
        for payload in current_payloads
        if str(payload.get("dex_id") or "").strip()
    }, key=str.lower)
    return {
        "candidates": candidates,
        "view": selected_view,
        "page": current_page,
        "page_size": safe_size,
        "page_count": page_count,
        "view_total": view_total,
        "search_query": search_query,
        "search_counts": filtered_counts,
        "qualified_total": qualified_total,
        "recent_total": recent_total,
        "archive_total": archive_total,
        "observed_volume_24h_usd": complete_sum("volume_24h_usd"),
        "observed_txns_24h": complete_sum("txns_24h"),
        "observed_dex_ids": dex_ids,
    }


def refresh_solana_discovery_archive(
    output_dir: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Writer path: qualify one completed collector snapshot and persist discovery history."""
    directory = Path(output_dir) if output_dir is not None else discovery_storage_dir(DEFAULT_OUTPUT_DIR)
    current_time = now or datetime.now(timezone.utc)
    state = _read_object(directory / "state.json")
    status = _read_object(directory / "status.json")

    if not isinstance(state.get("candidates"), dict) or not isinstance(status.get("metrics"), dict):
        raise ValueError("Collector output schema is not ready for archive refresh.")

    generated_at = status.get("generated_at")
    _, fresh = _freshness_label(generated_at, now=current_time)
    diagnostics: dict[str, dict[str, Any]] = {}
    if fresh:
        qualified = qualify_discovery_candidates(
            state["candidates"], now=current_time, diagnostics=diagnostics
        )
        default_diagnostic = None
    else:
        qualified = []
        default_diagnostic = _stale_qualification_diagnostic(generated_at)

    qualified_at = (
        str(generated_at).strip()
        if isinstance(generated_at, str) and generated_at.strip()
        else current_time.isoformat()
    )
    for diagnostic in diagnostics.values():
        diagnostic["scan_at"] = qualified_at
    if default_diagnostic is not None:
        default_diagnostic["scan_at"] = qualified_at

    _, archive_total = _update_archive(
        directory,
        qualified,
        qualified_at=qualified_at,
        diagnostics=diagnostics,
        default_diagnostic=default_diagnostic,
    )
    return {
        "archive_total": archive_total,
        "qualified_candidates": len(qualified),
    }


def load_solana_discovery_engine_feed(
    output_dir: Path | str | None = None,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    """Return a minimal qualified-token feed without rebuilding unchanged snapshots."""
    global _ENGINE_FEED_GENERATED_AT

    directory = Path(output_dir) if output_dir is not None else discovery_storage_dir(DEFAULT_OUTPUT_DIR)
    database = directory / DISCOVERY_ARCHIVE_DB
    safe_limit = min(100, max(1, _integer(limit) or 25))

    try:
        status = _read_object(directory / "status.json")
    except (OSError, json.JSONDecodeError, ValueError):
        status = {}

    generated_at = str(status.get("generated_at") or "").strip() or None

    with _ENGINE_FEED_LOCK:
        refresh_required = bool(
            generated_at and generated_at != _ENGINE_FEED_GENERATED_AT
        )

        if refresh_required and database.is_file():
            connection = None
            try:
                connection = sqlite3.connect(
                    database.resolve().as_uri() + "?mode=ro",
                    uri=True,
                )
                row = connection.execute(
                    """
                    SELECT MAX(last_qualified_at)
                    FROM discoveries
                    WHERE currently_qualified = 1
                    """
                ).fetchone()
                archived_at = str(row[0] or "").strip() if row else ""
                if archived_at == generated_at:
                    refresh_required = False
            except sqlite3.Error:
                refresh_required = True
            finally:
                if connection is not None:
                    connection.close()

        if refresh_required:
            # Archive persistence belongs to the collector. If status is newer than
            # the archive, fail closed briefly and retry on the next read.
            return {
                "connected": False,
                "generated_at": generated_at,
                "candidates": [],
            }
        if generated_at:
            _ENGINE_FEED_GENERATED_AT = generated_at

        if not database.is_file():
            return {
                "connected": False,
                "generated_at": generated_at,
                "candidates": [],
            }

        connection = None
        try:
            connection = sqlite3.connect(
                database.resolve().as_uri() + "?mode=ro",
                uri=True,
            )
            rows = connection.execute(
                """
                SELECT token_address, payload_json, last_qualified_at, last_seen_at
                FROM discoveries
                WHERE currently_qualified = 1
                ORDER BY COALESCE(last_seen_at, '') DESC,
                         last_qualified_at DESC,
                         token_address ASC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        except sqlite3.Error:
            return {
                "connected": False,
                "generated_at": generated_at,
                "candidates": [],
            }
        finally:
            if connection is not None:
                connection.close()

    candidates: list[dict[str, Any]] = []
    for token_address, payload_json, last_qualified_at, last_seen_at in rows:
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue

        address = str(token_address or "").strip()
        if not address:
            continue

        symbol = str(payload.get("symbol") or "Unknown").strip()[:40] or "Unknown"
        quote_symbol = str(payload.get("quote_symbol") or "SOL").strip()[:20] or "SOL"

        candidates.append(
            {
                "address": address,
                "label": f"{symbol} / {quote_symbol}",
                "href": f"/discovery/solana/{address}",
                "dex_id": str(payload.get("dex_id") or "").strip()[:40],
                "last_qualified_at": last_qualified_at,
                "last_seen_at": last_seen_at,
            }
        )

    return {
        "connected": True,
        "generated_at": generated_at,
        "candidates": candidates,
    }

def load_solana_discovery_feed(
    output_dir: Path | str | None = None,
    *,
    now: datetime | None = None,
    view: str | None = None,
    page: int = 1,
    page_size: int = TERMINAL_PAGE_SIZE,
    query: str = "",
) -> dict[str, Any]:
    """Return a conservative public read model without exposing raw candidates."""
    directory = Path(output_dir) if output_dir is not None else discovery_storage_dir(DEFAULT_OUTPUT_DIR)
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
    archive_feed, archive_total, qualified_count = _read_archive_front_feed(
        directory,
        fresh=fresh,
        generated_at=generated_at,
    )
    terminal_data = (
        _terminal_archive_view(
            directory, view=view, page=page, page_size=page_size, now=current_time, query=query,
            fresh=fresh, generated_at=generated_at
        )
        if view is not None else {}
    )
    return {
        "connected": True,
        "fresh": fresh,
        "collector_status": collector_status,
        "tokens_observed": len(state["candidates"]),
        "pair_resolved": _integer(metrics.get("pair_resolved")),
        "pair_ready_percent": metrics.get("pair_ready_percent"),
        "qualified_candidates": qualified_count,
        "candidates": terminal_data.get("candidates", archive_feed),
        "archive_total": archive_total,
        "feed_limit": DISCOVERY_FEED_LIMIT,
        "updated_label": updated_label,
        "message": (
            "Qualified Now reflects the current scan. Discovery Feed keeps previously qualified "
            "tokens for review; historical inclusion does not mean a token still qualifies now."
            if qualified_count else
            "Collector telemetry is connected. No observed token currently passes the "
            "required identity, liquidity, activity and freshness checks. Previously qualified "
            "discoveries remain in the persistent archive."
        ),
        **terminal_data,
    }
