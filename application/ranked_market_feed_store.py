"""Persistent cold-bootstrap cache for ranked Jupiter market feeds."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from application.discovery_storage import discovery_storage_dir


RANKED_MARKET_FEED_SCHEMA_VERSION = 1
RANKED_MARKET_FEED_FILENAME = "ranked-market-feeds-v1.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime) -> str:
    current = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def ranked_market_feed_store_path(root: Path | str | None = None) -> Path:
    base = Path(root) if root is not None else discovery_storage_dir()
    return base / "market" / RANKED_MARKET_FEED_FILENAME


class RankedMarketFeedStore:
    """Fail-open atomic LKG store for final ranked-feed payloads."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.path = Path(path) if path is not None else ranked_market_feed_store_path()
        self._now = now
        self._lock = threading.Lock()

    @staticmethod
    def _empty_payload() -> dict[str, Any]:
        return {"schema_version": RANKED_MARKET_FEED_SCHEMA_VERSION, "feeds": {}}

    def _load_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return self._empty_payload()
        if not isinstance(payload, dict):
            return self._empty_payload()
        if payload.get("schema_version") != RANKED_MARKET_FEED_SCHEMA_VERSION:
            return self._empty_payload()
        if not isinstance(payload.get("feeds"), dict):
            return self._empty_payload()
        return payload

    def load(self, key: str, *, max_age_seconds: float) -> tuple[dict[str, Any], float] | None:
        """Return one unexpired payload and its age, or None on any cache problem."""
        if max_age_seconds < 0:
            return None
        with self._lock:
            payload = self._load_unlocked()
            record = payload["feeds"].get(key)
            if not isinstance(record, dict):
                return None
            value = record.get("payload")
            if not isinstance(value, dict):
                return None
            saved_at = _parse_utc(record.get("saved_at"))
            if saved_at is None:
                return None
            now = self._now()
            now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
            age = (now - saved_at).total_seconds()
            if age < 0 or age > max_age_seconds:
                return None
            return dict(value), age

    def save(self, key: str, payload_value: dict[str, Any]) -> bool:
        """Persist one final feed payload atomically without breaking requests on failure."""
        with self._lock:
            payload = self._load_unlocked()
            payload["feeds"][key] = {
                "saved_at": _iso_utc(self._now()),
                "payload": dict(payload_value),
            }
            temp = self.path.with_name(
                f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            encoded = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ) + "\n"
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with temp.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, self.path)
            except OSError:
                try:
                    temp.unlink(missing_ok=True)
                except OSError:
                    pass
                return False
            return True
