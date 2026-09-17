"""Persistent rolling Recent-market observation store.

RECENT-V2-06A only.

This module is deliberately not wired into the production Recent feed yet.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from application.discovery_storage import discovery_storage_dir


RECENT_V2_SCHEMA_VERSION = 1
RECENT_V2_ENTRY_MIN_LIQUIDITY_USD = 25_000.0
RECENT_V2_RETENTION_SECONDS = 24 * 60 * 60
RECENT_V2_FILENAME = "recent-v2.json"


class RecentMarketStoreUnavailable(RuntimeError):
    """Raised when the Recent V2 store cannot be read or persisted safely."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime | None) -> datetime:
    current = value if isinstance(value, datetime) else _utc_now()
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return _coerce_utc(value).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def recent_market_store_path(root: Path | str | None = None) -> Path:
    """Return the isolated Recent V2 store path."""
    base = Path(root) if root is not None else discovery_storage_dir()
    return base / "market" / RECENT_V2_FILENAME


class RecentMarketStore:
    """Atomic JSON store for eligible Recent observations."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.path = Path(path) if path is not None else recent_market_store_path()
        self._now = now
        self._lock = threading.Lock()

    @staticmethod
    def _empty_payload() -> dict[str, Any]:
        return {"schema_version": RECENT_V2_SCHEMA_VERSION, "records": {}}

    def _load_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RecentMarketStoreUnavailable(
                "Recent V2 store is unreadable or corrupt."
            ) from error
        if not isinstance(payload, dict):
            raise RecentMarketStoreUnavailable("Recent V2 store root must be an object.")
        if payload.get("schema_version") != RECENT_V2_SCHEMA_VERSION:
            raise RecentMarketStoreUnavailable(
                "Recent V2 store schema version is unsupported."
            )
        records = payload.get("records")
        if not isinstance(records, dict):
            raise RecentMarketStoreUnavailable("Recent V2 store records are invalid.")
        for mint, record in records.items():
            if not isinstance(mint, str) or not mint.strip() or not isinstance(record, dict):
                raise RecentMarketStoreUnavailable(
                    "Recent V2 store contains an invalid record."
                )
        return payload

    def _persist_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        encoded = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ) + "\n"
        try:
            with temp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        except OSError as error:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise RecentMarketStoreUnavailable(
                "Recent V2 store could not be persisted atomically."
            ) from error

    @staticmethod
    def _anchor(record: dict[str, Any]) -> datetime | None:
        pool_time = _parse_utc(record.get("first_pool_created_at"))
        first_seen = _parse_utc(record.get("first_seen_at"))
        if pool_time is not None and first_seen is not None and pool_time <= first_seen:
            return pool_time
        if pool_time is not None and first_seen is None:
            return pool_time
        return first_seen

    @classmethod
    def _is_active(cls, record: dict[str, Any], *, now: datetime) -> bool:
        anchor = cls._anchor(record)
        if anchor is None:
            return False
        age = (now - anchor).total_seconds()
        return 0 <= age <= RECENT_V2_RETENTION_SECONDS

    @staticmethod
    def _row_identity(row: dict[str, Any]) -> tuple[str, str] | None:
        token_address = str(row.get("token_address") or "").strip()
        pair_address = str(row.get("pair_address") or "").strip()
        if not token_address or not pair_address:
            return None
        return token_address, pair_address

    def _new_record(
        self,
        row: dict[str, Any],
        *,
        observed_at: datetime,
    ) -> dict[str, Any] | None:
        identity = self._row_identity(row)
        if identity is None:
            return None
        liquidity = _number(row.get("liquidity_usd"))
        if liquidity is None or liquidity < RECENT_V2_ENTRY_MIN_LIQUIDITY_USD:
            return None

        token_address, pair_address = identity
        pool_time = _parse_utc(row.get("first_pool_created_at"))
        if pool_time is not None and pool_time > observed_at:
            pool_time = None
        anchor = pool_time or observed_at
        if (observed_at - anchor).total_seconds() > RECENT_V2_RETENTION_SECONDS:
            return None

        return {
            "schema_version": RECENT_V2_SCHEMA_VERSION,
            "token_address": token_address,
            "symbol": str(row.get("symbol") or "Unknown").strip()[:40],
            "name": str(row.get("name") or "Unknown token").strip()[:100],
            "icon": str(row.get("icon") or "").strip(),
            "pair_address": pair_address,
            "dex_id": str(row.get("dex_id") or "").strip(),
            "quote_address": str(row.get("quote_address") or "").strip(),
            "quote_symbol": str(row.get("quote_symbol") or "SOL").strip(),
            "first_pool_id": str(row.get("first_pool_id") or "").strip(),
            "first_pool_created_at": (
                _iso_utc(pool_time)
                if pool_time is not None
                else str(row.get("first_pool_created_at") or "").strip()
            ),
            "first_seen_at": _iso_utc(observed_at),
            "last_seen_at": _iso_utc(observed_at),
            "entry_liquidity_usd": liquidity,
            "liquidity_usd": liquidity,
            "price_usd": _number(row.get("price_usd")),
            "change_1h": _number(row.get("change_1h")),
            "volume_1h_usd": _number(row.get("volume_1h_usd")),
            "recent_source_position": row.get("recent_source_position"),
            "detected_signal": row.get("detected_signal"),
            "market_source": str(row.get("market_source") or "jupiter_recent").strip(),
            "href": str(row.get("href") or f"/market/recent/{token_address}").strip(),
        }

    @staticmethod
    def _update_record(
        existing: dict[str, Any],
        row: dict[str, Any],
        *,
        observed_at: datetime,
    ) -> dict[str, Any]:
        updated = dict(existing)
        pair_address = str(row.get("pair_address") or "").strip()
        if pair_address:
            updated["pair_address"] = pair_address
        for key, limit in (("symbol", 40), ("name", 100)):
            value = str(row.get(key) or "").strip()
            if value:
                updated[key] = value[:limit]
        for key in (
            "icon", "dex_id", "quote_address", "quote_symbol",
            "first_pool_id", "market_source", "href",
        ):
            value = str(row.get(key) or "").strip()
            if value:
                updated[key] = value
        for key in ("liquidity_usd", "price_usd", "change_1h", "volume_1h_usd"):
            value = _number(row.get(key))
            if value is not None:
                updated[key] = value
        if row.get("recent_source_position") is not None:
            updated["recent_source_position"] = row.get("recent_source_position")
        if row.get("detected_signal") is not None:
            updated["detected_signal"] = row.get("detected_signal")
        updated["last_seen_at"] = _iso_utc(observed_at)
        return updated

    def admit(
        self,
        row: dict[str, Any],
        *,
        observed_at: datetime | None = None,
    ) -> bool:
        """Admit a new row; existing admitted rows may update below $25k."""
        when = _coerce_utc(observed_at or self._now())
        identity = self._row_identity(row)
        if identity is None:
            return False
        token_address, _ = identity
        with self._lock:
            payload = self._load_unlocked()
            records = payload["records"]
            existing = records.get(token_address)
            if isinstance(existing, dict):
                records[token_address] = self._update_record(
                    existing, row, observed_at=when
                )
                self._persist_unlocked(payload)
                return True
            record = self._new_record(row, observed_at=when)
            if record is None:
                return False
            records[token_address] = record
            self._persist_unlocked(payload)
            return True

    def upsert(
        self,
        row: dict[str, Any],
        *,
        observed_at: datetime | None = None,
    ) -> bool:
        """Update an admitted row, or apply admission rules for a new row."""
        return self.admit(row, observed_at=observed_at)

    def get(
        self,
        token_address: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        address = str(token_address or "").strip()
        if not address:
            return None
        current = _coerce_utc(now or self._now())
        with self._lock:
            payload = self._load_unlocked()
            record = payload["records"].get(address)
            if not isinstance(record, dict) or not self._is_active(record, now=current):
                return None
            return dict(record)

    def active_rows(
        self,
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        current = _coerce_utc(now or self._now())
        with self._lock:
            payload = self._load_unlocked()
            rows = [
                dict(record)
                for record in payload["records"].values()
                if isinstance(record, dict) and self._is_active(record, now=current)
            ]
        rows.sort(
            key=lambda record: (
                self._anchor(record).timestamp()
                if self._anchor(record) is not None else 0.0
            ),
            reverse=True,
        )
        return rows

    def expire(self, *, now: datetime | None = None) -> int:
        """Remove records outside the rolling 24-hour active window."""
        current = _coerce_utc(now or self._now())
        with self._lock:
            payload = self._load_unlocked()
            records = payload["records"]
            expired = [
                mint
                for mint, record in records.items()
                if not isinstance(record, dict)
                or not self._is_active(record, now=current)
            ]
            if not expired:
                return 0
            for mint in expired:
                records.pop(mint, None)
            self._persist_unlocked(payload)
            return len(expired)

    def count(self, *, now: datetime | None = None) -> int:
        return len(self.active_rows(now=now))
