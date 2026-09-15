"""Single-process supervisor for the staged Solana discovery collector."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from application.discovery_storage import PROJECT_ROOT, discovery_storage_dir

COLLECTOR_SCRIPT = PROJECT_ROOT / "research" / "continuous_discovery_runtime.py"
PROVIDER_TIMEOUT_SECONDS = 45
_LOGGER = logging.getLogger("dexsato.production")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _boolean_environment(name: str, default: bool) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    raise RuntimeError(f"{name} must be true or false.")


def _positive_integer(name: str, default: int, *, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error
    if value < 1 or value > maximum:
        raise RuntimeError(f"{name} must be between 1 and {maximum}.")
    return value


def collector_enabled() -> bool:
    """Return whether this web process owns the collector scheduler."""
    return _boolean_environment("DEXSATO_COLLECTOR_ENABLED", False)


def discovery_stale_minutes() -> int:
    """Return the maximum age of the latest completed collector status."""
    return _positive_integer("DEXSATO_DISCOVERY_STALE_MINUTES", 45, maximum=10_080)


@dataclass(frozen=True)
class CollectorConfiguration:
    enabled: bool
    interval_seconds: int
    timeout_seconds: int
    limit: int
    output_directory: Path

    @classmethod
    def from_environment(cls) -> CollectorConfiguration:
        enabled, interval, timeout, limit = _collector_environment()
        return cls(
            enabled=enabled,
            interval_seconds=interval,
            timeout_seconds=timeout,
            limit=limit,
            output_directory=discovery_storage_dir(),
        )


def _collector_environment() -> tuple[bool, int, int, int]:
    enabled = collector_enabled()
    interval = _positive_integer(
        "DEXSATO_COLLECTOR_INTERVAL_SECONDS", 900, maximum=86_400
    )
    timeout = _positive_integer(
        "DEXSATO_COLLECTOR_TIMEOUT_SECONDS", 600, maximum=86_400
    )
    if timeout >= interval:
        raise RuntimeError(
            "DEXSATO_COLLECTOR_TIMEOUT_SECONDS must be less than "
            "DEXSATO_COLLECTOR_INTERVAL_SECONDS."
        )
    limit = _positive_integer("DEXSATO_COLLECTOR_LIMIT", 20, maximum=20)
    return enabled, interval, timeout, limit


def validate_collector_configuration() -> None:
    """Reject unsafe or ambiguous collector supervisor settings."""
    _collector_environment()
    discovery_stale_minutes()


ProcessFactory = Callable[..., Awaitable[asyncio.subprocess.Process]]


class CollectorScheduler:
    """Run one collector subprocess per interval without overlapping cycles."""

    def __init__(
        self,
        configuration: CollectorConfiguration,
        *,
        process_factory: ProcessFactory = asyncio.create_subprocess_exec,
    ) -> None:
        self.configuration = configuration
        self._process_factory = process_factory
        self._stop_event = asyncio.Event()
        self._cycle_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._active_process: asyncio.subprocess.Process | None = None

    @classmethod
    def from_environment(cls) -> CollectorScheduler:
        return cls(CollectorConfiguration.from_environment())

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def _emit(self, event: str, **metadata: object) -> None:
        payload = {
            "event": event,
            "timestamp_unix_ms": int(time.time() * 1000),
            **metadata,
        }
        level = logging.ERROR if event.endswith(("failed", "timeout")) else logging.INFO
        _LOGGER.log(level, json.dumps(payload, separators=(",", ":"), sort_keys=True))

    def command(self) -> tuple[str, ...]:
        return (
            sys.executable,
            str(COLLECTOR_SCRIPT),
            "--output-dir",
            str(self.configuration.output_directory),
            "--limit",
            str(self.configuration.limit),
            "--timeout-seconds",
            str(PROVIDER_TIMEOUT_SECONDS),
        )

    def _completed_collector_status(self) -> str | None:
        try:
            payload = json.loads(
                (self.configuration.output_directory / "status.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        status = payload.get("collector_status")
        return status if isinstance(status, str) else None

    async def start(self) -> None:
        if not self.configuration.enabled or self.running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(), name="dexsato-collector-scheduler"
        )
        self._emit(
            "collector_scheduler_started",
            interval_seconds=self.configuration.interval_seconds,
            timeout_seconds=self.configuration.timeout_seconds,
        )

    async def stop(self) -> None:
        self._stop_event.set()
        process = self._active_process
        if process is not None and process.returncode is None:
            await self._terminate(process)
        task = self._task
        if task is not None:
            await task
        self._task = None
        if self.configuration.enabled:
            self._emit("collector_scheduler_stopped")

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

    async def run_cycle(self) -> str:
        """Run one bounded cycle, returning a metadata-safe outcome."""
        if self._cycle_lock.locked():
            self._emit("collector_cycle_skipped", reason="overlap")
            return "skipped"

        async with self._cycle_lock:
            started = time.monotonic()
            try:
                process = await self._process_factory(
                    *self.command(),
                    cwd=str(PROJECT_ROOT),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._active_process = process
                try:
                    if self._stop_event.is_set():
                        await self._terminate(process)
                        return "stopped"
                    return_code = await asyncio.wait_for(
                        process.wait(), timeout=self.configuration.timeout_seconds
                    )
                except asyncio.TimeoutError:
                    await self._terminate(process)
                    self._emit(
                        "collector_cycle_timeout",
                        duration_ms=round((time.monotonic() - started) * 1000, 2),
                        timeout_seconds=self.configuration.timeout_seconds,
                    )
                    return "timeout"
                finally:
                    self._active_process = None
            except Exception as error:  # noqa: BLE001 - keep the web process alive.
                self._emit(
                    "collector_cycle_failed",
                    duration_ms=round((time.monotonic() - started) * 1000, 2),
                    exception_type=type(error).__name__,
                )
                return "failed"

            event = (
                "collector_cycle_succeeded"
                if return_code == 0
                else "collector_cycle_failed"
            )
            self._emit(
                event,
                duration_ms=round((time.monotonic() - started) * 1000, 2),
                return_code=return_code,
                collector_status=(
                    self._completed_collector_status() if return_code == 0 else None
                ),
            )
            return "success" if return_code == 0 else "failed"

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            started = time.monotonic()
            await self.run_cycle()
            remaining = max(
                0.0, self.configuration.interval_seconds - (time.monotonic() - started)
            )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                continue
