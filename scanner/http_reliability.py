"""Bounded retry policy for temporary external-provider failures."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import requests


LOGGER = logging.getLogger("dexsato.external_api")
TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}
TRANSIENT_EXCEPTIONS = (requests.Timeout, requests.ConnectionError)


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

    for attempt in range(1, max_attempts + 1):
        try:
            response = operation()
        except TRANSIENT_EXCEPTIONS as error:
            if attempt >= max_attempts:
                LOGGER.error(
                    "external_api_failed provider=%s attempts=%s reason=%s",
                    provider, attempt, type(error).__name__,
                )
                raise
            LOGGER.warning(
                "external_api_retry provider=%s attempt=%s/%s reason=%s backoff=%.1fs",
                provider, attempt, max_attempts, type(error).__name__, backoff_seconds,
            )
            sleep(backoff_seconds)
            continue

        status_code = getattr(response, "status_code", None)
        if status_code in TRANSIENT_HTTP_STATUSES and attempt < max_attempts:
            LOGGER.warning(
                "external_api_retry provider=%s attempt=%s/%s reason=http_%s backoff=%.1fs",
                provider, attempt, max_attempts, status_code, backoff_seconds,
            )
            sleep(backoff_seconds)
            continue
        if status_code in TRANSIENT_HTTP_STATUSES:
            LOGGER.error(
                "external_api_failed provider=%s attempts=%s reason=http_%s",
                provider, attempt, status_code,
            )
        return response

    raise RuntimeError("Bounded retry loop exited unexpectedly.")
