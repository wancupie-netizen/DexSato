"""Bounded retry policy for temporary external-provider failures."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import requests


LOGGER = logging.getLogger("dexsato.external_api")
TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}
TRANSIENT_EXCEPTIONS = (requests.Timeout, requests.ConnectionError)
_TELEMETRY_LOCK = Lock()
_PROVIDER_TELEMETRY: dict[str, dict[str, object]] = {}


def _provider_record(provider: str) -> dict[str, object]:
    return _PROVIDER_TELEMETRY.setdefault(provider, {
        "provider": provider,
        "status": "HEALTHY",
        "logical_requests": 0,
        "attempts": 0,
        "retries": 0,
        "failures": 0,
        "last_failure": None,
        "last_failure_at": None,
    })


def _record(provider: str, **changes: object) -> None:
    with _TELEMETRY_LOCK:
        record = _provider_record(provider)
        for key in ("logical_requests", "attempts", "retries", "failures"):
            if key in changes:
                record[key] = int(record[key]) + int(changes[key])
        for key in ("status", "last_failure", "last_failure_at"):
            if key in changes:
                record[key] = changes[key]


def reset_provider_telemetry() -> None:
    """Start one isolated telemetry window for a new snapshot scan."""
    with _TELEMETRY_LOCK:
        _PROVIDER_TELEMETRY.clear()


def get_provider_health() -> dict[str, object]:
    """Return a JSON-safe provider health summary for the current scan."""
    with _TELEMETRY_LOCK:
        providers = [dict(value) for value in _PROVIDER_TELEMETRY.values()]
    providers.sort(key=lambda item: str(item["provider"]))
    statuses = {str(item["status"]) for item in providers}
    overall = (
        "DEGRADED" if "DEGRADED" in statuses
        else "RECOVERED" if "RECOVERED" in statuses
        else "HEALTHY" if providers else "NO_ACTIVITY"
    )
    return {
        "status": overall,
        "providers": providers,
        "total_requests": sum(int(item["logical_requests"]) for item in providers),
        "total_attempts": sum(int(item["attempts"]) for item in providers),
        "total_retries": sum(int(item["retries"]) for item in providers),
        "total_failures": sum(int(item["failures"]) for item in providers),
        "policy": "SCAN_WINDOW_AGGREGATE_NO_PAYLOADS_OR_URLS",
    }


def request_with_bounded_retry(
    operation: Callable[[], Any], *, provider: str,
    max_attempts: int = 2, backoff_seconds: float = 0.4,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Run one request with one bounded retry for temporary failures only."""
    if max_attempts < 1 or max_attempts > 3:
        raise ValueError("External API attempts must be between 1 and 3.")
    if backoff_seconds < 0 or backoff_seconds > 5:
        raise ValueError("External API backoff must be between 0 and 5 seconds.")

    _record(provider, logical_requests=1)
    for attempt in range(1, max_attempts + 1):
        _record(provider, attempts=1)
        try:
            response = operation()
        except TRANSIENT_EXCEPTIONS as error:
            if attempt >= max_attempts:
                _record(
                    provider, failures=1, status="DEGRADED",
                    last_failure=type(error).__name__,
                    last_failure_at=datetime.now(timezone.utc).isoformat(),
                )
                LOGGER.error(
                    "external_api_failed provider=%s attempts=%s reason=%s",
                    provider, attempt, type(error).__name__,
                )
                raise
            _record(provider, retries=1, status="RECOVERED")
            LOGGER.warning(
                "external_api_retry provider=%s attempt=%s/%s reason=%s backoff=%.1fs",
                provider, attempt, max_attempts, type(error).__name__, backoff_seconds,
            )
            sleep(backoff_seconds)
            continue
        except Exception as error:
            _record(
                provider, failures=1, status="DEGRADED",
                last_failure=type(error).__name__,
                last_failure_at=datetime.now(timezone.utc).isoformat(),
            )
            raise

        status_code = getattr(response, "status_code", None)
        if status_code in TRANSIENT_HTTP_STATUSES and attempt < max_attempts:
            _record(provider, retries=1, status="RECOVERED")
            LOGGER.warning(
                "external_api_retry provider=%s attempt=%s/%s reason=http_%s backoff=%.1fs",
                provider, attempt, max_attempts, status_code, backoff_seconds,
            )
            sleep(backoff_seconds)
            continue
        if status_code in TRANSIENT_HTTP_STATUSES:
            _record(
                provider, failures=1, status="DEGRADED",
                last_failure=f"HTTP {status_code}",
                last_failure_at=datetime.now(timezone.utc).isoformat(),
            )
            LOGGER.error(
                "external_api_failed provider=%s attempts=%s reason=http_%s",
                provider, attempt, status_code,
            )
        elif isinstance(status_code, int) and status_code >= 400:
            _record(
                provider, failures=1, status="DEGRADED",
                last_failure=f"HTTP {status_code}",
                last_failure_at=datetime.now(timezone.utc).isoformat(),
            )
        return response

    raise RuntimeError("Bounded retry loop exited unexpectedly.")
