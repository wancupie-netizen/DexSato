"""Production request-boundary controls for the DexSato web application."""

from __future__ import annotations

import hmac
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request


def _positive_int(name: str, default: int, *, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error
    if value < 1 or value > maximum:
        raise RuntimeError(f"{name} must be between 1 and {maximum}.")
    return value


def production_mode() -> bool:
    return os.getenv("DEXSATO_ENV", "development").strip().lower() == "production"


def application_host() -> str:
    return os.getenv("HOST", "0.0.0.0" if production_mode() else "127.0.0.1").strip()


def application_port() -> int:
    return _positive_int("PORT", 8000, maximum=65535)


def maximum_request_bytes() -> int:
    return _positive_int("DEXSATO_MAX_REQUEST_BYTES", 16_384, maximum=1_048_576)


def internal_endpoints_enabled() -> bool:
    raw = os.getenv("DEXSATO_INTERNAL_ENDPOINTS_ENABLED", "false" if production_mode() else "true")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def require_internal_access(request: Request) -> None:
    """Hide internal routes in production unless an operator explicitly enables them."""
    if not production_mode():
        return
    if not internal_endpoints_enabled():
        raise HTTPException(status_code=404, detail="Not found.")

    expected = os.getenv("DEXSATO_OPERATOR_TOKEN", "").strip()
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Internal access is not configured.")

    authorization = request.headers.get("authorization", "")
    scheme, separator, supplied = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Operator authentication required.")


@dataclass(frozen=True)
class _RateRule:
    name: str
    limit: int
    seconds: int


_CONTENT_LOGIN_RULE = _RateRule("content-login", 5, 900)
_CONTENT_GENERATE_RULE = _RateRule("content-generate", 20, 60)
_TELEGRAM_RULE = _RateRule("telegram-send", 3, 60)
_JUPITER_QUOTE_RULE = _RateRule("jupiter-quote", 30, 60)
_JUPITER_ORDER_RULE = _RateRule("jupiter-order", 10, 60)
_JUPITER_EXECUTE_RULE = _RateRule("jupiter-execute", 10, 60)
_SOLANA_API_RULE = _RateRule("solana-api", 90, 60)
_GENERAL_API_RULE = _RateRule("api", 120, 60)


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client: str, rule: _RateRule, now: float) -> bool:
        key = (client, rule.name)
        cutoff = now - rule.seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= rule.limit:
                return False
            events.append(now)
            return True


class ApplicationBoundaryMiddleware:
    """Apply bounded bodies and conservative per-process request throttles."""

    def __init__(self, app: object) -> None:
        self.app = app
        self._limiter = _SlidingWindowLimiter()

    @staticmethod
    def _rule(path: str, method: str) -> _RateRule | None:
        if path == "/content-control/login" and method == "POST":
            return _CONTENT_LOGIN_RULE
        if path == "/content-control/generate" and method == "POST":
            return _CONTENT_GENERATE_RULE
        if path == "/telegram/send" and method == "POST":
            return _TELEGRAM_RULE
        if path.startswith("/api/discovery/solana/"):
            if path.endswith("/jupiter-quote"):
                return _JUPITER_QUOTE_RULE
            if path.endswith("/jupiter-order") and method == "POST":
                return _JUPITER_ORDER_RULE
            if path.endswith("/jupiter-execute") and method == "POST":
                return _JUPITER_EXECUTE_RULE
            return _SOLANA_API_RULE
        if path.startswith("/api/"):
            return _GENERAL_API_RULE
        return None

    @staticmethod
    async def _json_response(send: object, status: int, detail: str, headers: list[tuple[bytes, bytes]] | None = None) -> None:
        body = ('{"detail":"' + detail + '"}').encode("utf-8")
        response_headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode("ascii"))]
        response_headers.extend(headers or [])
        await send({"type": "http.response.start", "status": status, "headers": response_headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: dict[str, object], receive: object, send: object) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        method = str(scope.get("method") or "GET").upper()
        client_value = scope.get("client")
        client = str(client_value[0]) if isinstance(client_value, tuple) and client_value else "unknown"
        rule = self._rule(path, method)
        if rule is not None and not self._limiter.allow(client, rule, time.monotonic()):
            await self._json_response(send, 429, "Too many requests.", [(b"retry-after", str(rule.seconds).encode("ascii"))])
            return

        limit = maximum_request_bytes()
        headers = {bytes(key).lower(): bytes(value) for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    await self._json_response(send, 413, "Request body is too large.")
                    return
            except ValueError:
                await self._json_response(send, 400, "Invalid Content-Length header.")
                return

        consumed = 0

        async def bounded_receive() -> dict[str, object]:
            nonlocal consumed
            message = await receive()
            if message.get("type") == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except _RequestBodyTooLarge:
            await self._json_response(send, 413, "Request body is too large.")


class _RequestBodyTooLarge(Exception):
    pass
