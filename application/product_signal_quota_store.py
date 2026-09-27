"""Persistent per-subject rolling quota ledger for Public detected signals."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable
from uuid import UUID

from application.discovery_storage import discovery_storage_dir


PRODUCT_SIGNAL_QUOTA_SCHEMA_VERSION = 1
PRODUCT_SIGNAL_QUOTA_WINDOW_SECONDS = 24 * 60 * 60
PRODUCT_SIGNAL_QUOTA_FILENAME = "detected-signal-quota-v1.json"

_PROCESS_LOCK = threading.Lock()


class ProductSignalQuotaStoreUnavailable(RuntimeError):
    """Raised when the quota ledger cannot be read or persisted safely."""


@dataclass(frozen=True, slots=True)
class ProductSignalQuotaAdmission:
    """Result of one atomic quota admission attempt."""

    allowed_keys: tuple[str, ...]
    newly_admitted_keys: tuple[str, ...]
    active_count: int
    remaining: int


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


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
    return _coerce_utc(parsed)


def _validate_subject_key(value: str) -> str:
    subject = str(value or "").strip()
    prefix, separator, identifier = subject.partition(":")
    if separator != ":" or prefix not in {"guest", "user"} or not identifier:
        raise ValueError("quota subject must be guest:<uuid> or user:<uuid>")
    try:
        parsed = UUID(identifier)
    except ValueError as error:
        raise ValueError("quota subject UUID is invalid") from error
    if str(parsed) != identifier.casefold():
        raise ValueError("quota subject UUID must use canonical text form")
    return f"{prefix}:{str(parsed)}"


def _validate_signal_key(value: str) -> str:
    signal_key = str(value or "").strip()
    prefix, separator, token_address = signal_key.partition(":")
    if (
        separator != ":"
        or prefix != "solana"
        or not token_address
        or token_address != token_address.strip()
        or any(character.isspace() for character in token_address)
        or len(token_address) > 128
    ):
        raise ValueError("quota signal key must be solana:<token_address>")
    return f"solana:{token_address}"


def product_signal_quota_store_path(root: Path | str | None = None) -> Path:
    """Return the isolated V1 detected-signal quota ledger path."""

    base = Path(root) if root is not None else discovery_storage_dir()
    return base / "product" / PRODUCT_SIGNAL_QUOTA_FILENAME


class ProductSignalQuotaStore:
    """Atomic JSON ledger for per-subject rolling detected-signal admissions."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.path = Path(path) if path is not None else product_signal_quota_store_path()
        self._now = now

    @staticmethod
    def _empty_payload() -> dict[str, Any]:
        return {
            "schema_version": PRODUCT_SIGNAL_QUOTA_SCHEMA_VERSION,
            "subjects": {},
        }

    def _load_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ProductSignalQuotaStoreUnavailable(
                "Detected-signal quota ledger is unreadable or corrupt."
            ) from error

        if not isinstance(payload, dict):
            raise ProductSignalQuotaStoreUnavailable(
                "Detected-signal quota ledger root must be an object."
            )
        if payload.get("schema_version") != PRODUCT_SIGNAL_QUOTA_SCHEMA_VERSION:
            raise ProductSignalQuotaStoreUnavailable(
                "Detected-signal quota ledger schema version is unsupported."
            )

        subjects = payload.get("subjects")
        if not isinstance(subjects, dict):
            raise ProductSignalQuotaStoreUnavailable(
                "Detected-signal quota ledger subjects are invalid."
            )

        for subject_key, subject_record in subjects.items():
            try:
                canonical_subject = _validate_subject_key(subject_key)
            except ValueError as error:
                raise ProductSignalQuotaStoreUnavailable(
                    "Detected-signal quota ledger contains an invalid subject."
                ) from error
            if canonical_subject != subject_key or not isinstance(subject_record, dict):
                raise ProductSignalQuotaStoreUnavailable(
                    "Detected-signal quota ledger contains an invalid subject record."
                )

            signals = subject_record.get("signals")
            if not isinstance(signals, dict):
                raise ProductSignalQuotaStoreUnavailable(
                    "Detected-signal quota ledger signals are invalid."
                )

            for signal_key, signal_record in signals.items():
                try:
                    canonical_signal = _validate_signal_key(signal_key)
                except ValueError as error:
                    raise ProductSignalQuotaStoreUnavailable(
                        "Detected-signal quota ledger contains an invalid signal key."
                    ) from error
                if canonical_signal != signal_key or not isinstance(signal_record, dict):
                    raise ProductSignalQuotaStoreUnavailable(
                        "Detected-signal quota ledger contains an invalid signal record."
                    )
                if _parse_utc(signal_record.get("first_admitted_at")) is None:
                    raise ProductSignalQuotaStoreUnavailable(
                        "Detected-signal quota ledger contains an invalid admission time."
                    )

        return payload

    def _persist_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
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
            raise ProductSignalQuotaStoreUnavailable(
                "Detected-signal quota ledger could not be persisted atomically."
            ) from error

    @staticmethod
    def _prune_expired(
        payload: dict[str, Any],
        *,
        now: datetime,
    ) -> bool:
        changed = False
        subjects = payload["subjects"]

        for subject_key in list(subjects):
            subject_record = subjects[subject_key]
            signals = subject_record["signals"]

            for signal_key in list(signals):
                admitted_at = _parse_utc(signals[signal_key].get("first_admitted_at"))
                if admitted_at is None:
                    raise ProductSignalQuotaStoreUnavailable(
                        "Detected-signal quota ledger contains an invalid admission time."
                    )
                age_seconds = (now - admitted_at).total_seconds()
                if age_seconds < 0:
                    raise ProductSignalQuotaStoreUnavailable(
                        "Detected-signal quota ledger contains a future admission time."
                    )
                if age_seconds >= PRODUCT_SIGNAL_QUOTA_WINDOW_SECONDS:
                    signals.pop(signal_key, None)
                    changed = True

            if not signals:
                subjects.pop(subject_key, None)
                changed = True

        return changed

    def admit(
        self,
        subject_key: str,
        signal_keys: Iterable[str],
        *,
        limit: int,
        now: datetime | None = None,
    ) -> ProductSignalQuotaAdmission:
        """Atomically admit ordered unique signal keys inside the rolling window."""

        canonical_subject = _validate_subject_key(subject_key)
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("quota limit must be a non-negative integer")

        ordered_keys: list[str] = []
        seen: set[str] = set()
        for value in signal_keys:
            signal_key = _validate_signal_key(value)
            if signal_key in seen:
                continue
            seen.add(signal_key)
            ordered_keys.append(signal_key)

        current = _coerce_utc(now if isinstance(now, datetime) else self._now())

        with _PROCESS_LOCK:
            payload = self._load_unlocked()
            changed = self._prune_expired(payload, now=current)

            subjects = payload["subjects"]
            subject_record = subjects.get(canonical_subject)
            if subject_record is None:
                signals: dict[str, dict[str, str]] = {}
            else:
                signals = subject_record["signals"]

            remaining_slots = max(0, limit - len(signals))
            allowed: list[str] = []
            newly_admitted: list[str] = []

            for signal_key in ordered_keys:
                if signal_key in signals:
                    allowed.append(signal_key)
                    continue
                if remaining_slots <= 0:
                    continue
                signals[signal_key] = {"first_admitted_at": _iso_utc(current)}
                allowed.append(signal_key)
                newly_admitted.append(signal_key)
                remaining_slots -= 1
                changed = True

            if signals and subject_record is None:
                subjects[canonical_subject] = {"signals": signals}

            if changed:
                self._persist_unlocked(payload)

            active_count = len(signals)
            return ProductSignalQuotaAdmission(
                allowed_keys=tuple(allowed),
                newly_admitted_keys=tuple(newly_admitted),
                active_count=active_count,
                remaining=max(0, limit - active_count),
            )
