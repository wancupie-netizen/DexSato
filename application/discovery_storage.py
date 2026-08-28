"""Shared persistent-storage and single-worker production contract."""

from __future__ import annotations

import os
import secrets
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_DISCOVERY_STORAGE = Path("output/research/solana-discovery-phase0-seven-day")
_WORKER_ENVIRONMENTS = ("DEXSATO_WEB_WORKERS", "WEB_CONCURRENCY", "UVICORN_WORKERS")


def _production_mode() -> bool:
    return os.getenv("DEXSATO_ENV", "development").strip().lower() == "production"


def discovery_storage_dir(default: Path | str = LEGACY_DISCOVERY_STORAGE) -> Path:
    """Resolve one directory shared by the web process and collector."""
    configured = os.getenv("DEXSATO_DISCOVERY_STORAGE_DIR", "").strip()
    if configured:
        selected = Path(configured).expanduser()
        if _production_mode() and not selected.is_absolute():
            raise RuntimeError("DEXSATO_DISCOVERY_STORAGE_DIR must be an absolute path in production.")
    else:
        if _production_mode():
            raise RuntimeError("DEXSATO_DISCOVERY_STORAGE_DIR is required in production.")
        selected = Path(default)
    return selected.resolve() if selected.is_absolute() else (PROJECT_ROOT / selected).resolve()


def _configured_workers() -> int:
    for name in _WORKER_ENVIRONMENTS:
        raw = os.getenv(name, "").strip()
        if not raw:
            continue
        try:
            workers = int(raw)
        except ValueError as error:
            raise RuntimeError(f"{name} must be the integer 1.") from error
        if workers != 1:
            raise RuntimeError(
                "DexSato requires exactly one web worker while Jupiter pending orders "
                "and rate limits are process-local."
            )
    return 1


def validate_production_runtime() -> Path:
    """Fail closed when production persistence or worker topology is unsafe."""
    directory = discovery_storage_dir()
    if not _production_mode():
        return directory
    _configured_workers()
    if not directory.is_dir():
        raise RuntimeError(
            "DEXSATO_DISCOVERY_STORAGE_DIR must reference an existing persistent volume directory."
        )
    probe = directory / f".dexsato-write-probe-{secrets.token_hex(8)}"
    try:
        probe.write_bytes(b"ready")
        probe.unlink()
    except OSError as error:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError("DexSato discovery storage is not writable.") from error
    return directory
