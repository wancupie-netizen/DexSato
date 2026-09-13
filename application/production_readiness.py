"""Credential-safe production configuration and local integrity checks."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from application.collector_scheduler import (
    discovery_stale_minutes,
    validate_collector_configuration,
)
from application.jupiter_fee_policy import (
    FeePolicyConfigurationError,
    get_fee_policy,
    read_fee_policy,
)
from application.production_security import internal_endpoints_enabled, production_mode

_PLACEHOLDER_PREFIXES = ("your-", "replace-with-", "changeme")


def _required_secret(name: str) -> None:
    value = os.getenv(name, "").strip()
    if not value or value.lower().startswith(_PLACEHOLDER_PREFIXES):
        raise RuntimeError(f"{name} is required in production.")


def _https_url(name: str, default: str = "") -> None:
    value = os.getenv(name, default).strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RuntimeError(f"{name} must be an HTTPS URL without embedded credentials.")



def _redis_pending_store_configuration() -> None:
    mode = os.getenv("DEXSATO_PENDING_STORE", "").strip().lower()
    if mode != "redis":
        raise RuntimeError("DEXSATO_PENDING_STORE=redis is required in production.")
    value = os.getenv("REDIS_URL", "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise RuntimeError("REDIS_URL must be a valid redis:// or rediss:// URL in production.")

def _redis_rate_limit_configuration() -> None:
    mode = os.getenv("DEXSATO_RATE_LIMIT_STORE", "").strip().lower()
    if mode != "redis":
        raise RuntimeError("DEXSATO_RATE_LIMIT_STORE=redis is required in production.")


def validate_production_configuration() -> None:
    """Reject missing core provider configuration without returning secret values."""
    # Validate even in development; malformed enable flags must not disable fees silently.
    if read_fee_policy() != get_fee_policy():
        raise FeePolicyConfigurationError("Jupiter fee configuration changed; restart the server.")
    validate_collector_configuration()
    if not production_mode():
        return
    _required_secret("JUPITER_API_KEY")
    _required_secret("BIRDEYE_API_KEY")
    _https_url("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    _redis_pending_store_configuration()
    _redis_rate_limit_configuration()
    if internal_endpoints_enabled():
        operator_token = os.getenv("DEXSATO_OPERATOR_TOKEN", "").strip()
        if len(operator_token) < 32:
            raise RuntimeError(
                "DEXSATO_OPERATOR_TOKEN must contain at least 32 characters when internal endpoints are enabled."
            )


def production_configuration_ready() -> bool:
    try:
        validate_production_configuration()
    except RuntimeError:
        return False
    return True


def _valid_json_object(path: Path, *, required_mapping: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and isinstance(payload.get(required_mapping), dict)


def collector_storage_ready(directory: Path) -> bool:
    """Validate stored collector schemas without contacting an upstream provider."""
    return _valid_json_object(directory / "state.json", required_mapping="candidates") and _valid_json_object(
        directory / "status.json", required_mapping="metrics"
    )


def collector_fresh(
    directory: Path,
    *,
    stale_minutes: int | None = None,
    now: datetime | None = None,
) -> bool:
    """Return whether status.json was generated within the configured window."""
    try:
        payload = json.loads((directory / "status.json").read_text(encoding="utf-8"))
        generated_at = payload.get("generated_at")
        if not isinstance(generated_at, str):
            return False
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        if generated.tzinfo is None:
            return False
        current = now or datetime.now(timezone.utc)
        age = current.astimezone(timezone.utc) - generated.astimezone(timezone.utc)
        maximum_age = timedelta(
            minutes=stale_minutes if stale_minutes is not None else discovery_stale_minutes()
        )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return False
    return timedelta(0) <= age <= maximum_age


def discovery_archive_ready(directory: Path, archive_filename: str) -> bool:
    """Open SQLite read-only, run its integrity check, and require the archive table."""
    archive = directory / archive_filename
    if not archive.is_file():
        return False
    try:
        uri = f"{archive.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1.0) as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'discoveries'"
            ).fetchone()
    except (OSError, sqlite3.Error, ValueError):
        return False
    return integrity == ("ok",) and table == (1,)
