"""Production request-boundary controls for the DexSato web application."""

from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request


_PRODUCTION_LOGGER = logging.getLogger("dexsato.production")
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def production_log_level() -> str:
    value = os.getenv("DEXSATO_LOG_LEVEL", "INFO").strip().upper()
    if value not in _LOG_LEVELS:
        raise RuntimeError("DEXSATO_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL.")
    if production_mode() and value == "DEBUG":
        raise RuntimeError("DEBUG logging is not allowed in production.")
    return value


def configure_production_logging() -> None:
    """Write bounded JSON application events to stdout without request contents."""
    level = production_log_level()
    if not any(getattr(handler, "_dexsato_handler", False) for handler in _PRODUCTION_LOGGER.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._dexsato_handler = True  # type: ignore[attr-defined]
        _PRODUCTION_LOGGER.addHandler(handler)
    _PRODUCTION_LOGGER.setLevel(getattr(logging, level))
    _PRODUCTION_LOGGER.propagate = False


def _request_id(scope: dict[str, object]) -> str:
    state = scope.setdefault("state", {})
    if not isinstance(state, dict):
        state = {}
        scope["state"] = state
    current = state.get("dexsato_request_id")
    if isinstance(current, str) and len(current) == 32:
        return current
    generated = secrets.token_hex(16)
    state["dexsato_request_id"] = generated
    return generated


def _safe_route(path: str) -> str:
    """Classify routes without logging token mints, query strings, or unknown paths."""
    segments = [segment for segment in path.split("/") if segment]
    if path in {"/", "/health", "/health/live", "/health/ready", "/discovery/solana"}:
        return path
    if len(segments) >= 4 and segments[:3] == ["api", "discovery", "solana"]:
        suffix = "/" + "/".join(segments[4:]) if len(segments) > 4 else ""
        return "/api/discovery/solana/:token" + suffix
    if len(segments) == 3 and segments[:2] == ["discovery", "solana"]:
        return "/discovery/solana/:token"
    if path in {"/content-control/login", "/content-control/generate", "/telegram/send"}:
        return path
    if path.startswith("/static/"):
        return "/static/:asset"
    return "unclassified"


class ProductionLoggingMiddleware:
    """Emit one metadata-only JSON event per HTTP request and exception."""

    def __init__(self, app: object) -> None:
        self.app = app

    @staticmethod
    def _emit(level: int, payload: dict[str, object]) -> None:
        _PRODUCTION_LOGGER.log(level, json.dumps(payload, separators=(",", ":"), sort_keys=True))

    async def __call__(self, scope: dict[str, object], receive: object, send: object) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        request_id = _request_id(scope)
        method = str(scope.get("method") or "GET").upper()
        route = _safe_route(str(scope.get("path") or ""))
        status = 500

        async def logged_send(message: dict[str, object]) -> None:
            nonlocal status
            if message.get("type") == "http.response.start":
                status = int(message.get("status") or 500)
            await send(message)

        try:
            await self.app(scope, receive, logged_send)
        except Exception as error:
            self._emit(
                logging.ERROR,
                {
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    "event": "http_exception",
                    "exception_type": type(error).__name__,
                    "method": method,
                    "request_id": request_id,
                    "route": route,
                    "status": 500,
                    "timestamp_unix_ms": int(time.time() * 1000),
                },
            )
            raise

        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        self._emit(
            level,
            {
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "event": "http_request_rejected" if status in {400, 401, 403, 404, 413, 429} else "http_request",
                "method": method,
                "request_id": request_id,
                "route": route,
                "status": status,
                "timestamp_unix_ms": int(time.time() * 1000),
            },
        )


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


def maximum_rate_limit_buckets() -> int:
    """Bound per-process limiter memory without silently evicting active clients."""
    return _positive_int("DEXSATO_RATE_LIMIT_MAX_BUCKETS", 10_000, maximum=100_000)


def internal_endpoints_enabled() -> bool:
    raw = os.getenv("DEXSATO_INTERNAL_ENDPOINTS_ENABLED", "false" if production_mode() else "true")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def trusted_proxy_headers() -> bool:
    raw = os.getenv("DEXSATO_TRUST_PROXY_HEADERS", "false")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def allowed_hosts() -> list[str]:
    raw = os.getenv("DEXSATO_ALLOWED_HOSTS", "").strip()
    if not raw:
        if production_mode():
            raise RuntimeError("DEXSATO_ALLOWED_HOSTS is required in production.")
        return ["127.0.0.1", "localhost", "testserver"]
    hosts = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not hosts or any("/" in host or "://" in host for host in hosts):
        raise RuntimeError("DEXSATO_ALLOWED_HOSTS must contain comma-separated hostnames.")
    if production_mode() and "*" in hosts:
        raise RuntimeError("Wildcard trusted hosts are not allowed in production.")
    return hosts


_ACTIONABLE_JUPITER_ERRORS = frozenset(
    {
        "Insufficient SOL balance. Reduce the swap amount or add SOL to your connected wallet.",
        "This wallet has too many pending swap reviews. Complete or wait for an existing review to expire.",
    }
)


def safe_jupiter_error_detail(error: BaseException) -> str:
    """Expose only reviewed Jupiter messages required for a user correction."""
    detail = str(error).strip()
    if detail in _ACTIONABLE_JUPITER_ERRORS:
        return detail
    return "Jupiter swap is temporarily unavailable."


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
    _STALE_AFTER_SECONDS = 900
    _SWEEP_INTERVAL_SECONDS = 60

    def __init__(self, *, maximum_buckets: int | None = None) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._last_seen: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()
        self._maximum_buckets = maximum_buckets or maximum_rate_limit_buckets()
        self._last_sweep = 0.0

    def _sweep(self, now: float) -> None:
        if now - self._last_sweep < self._SWEEP_INTERVAL_SECONDS:
            return
        cutoff = now - self._STALE_AFTER_SECONDS
        stale = [key for key, last_seen in self._last_seen.items() if last_seen <= cutoff]
        for key in stale:
            self._events.pop(key, None)
            self._last_seen.pop(key, None)
        self._last_sweep = now

    def allow(self, client: str, rule: _RateRule, now: float) -> bool:
        key = (client, rule.name)
        cutoff = now - rule.seconds
        with self._lock:
            self._sweep(now)
            if key not in self._events and len(self._events) >= self._maximum_buckets:
                return False
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= rule.limit:
                self._last_seen[key] = now
                return False
            events.append(now)
            self._last_seen[key] = now
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


class SecurityHeadersMiddleware:
    """Attach browser hardening headers to every HTTP response."""

    _CSP = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://api.jup.ag https://api.mainnet-beta.solana.com"
    )

    def __init__(self, app: object) -> None:
        self.app = app

    @staticmethod
    def _requires_no_store(path: str) -> bool:
        if path.startswith("/content-control") or path == "/telegram/send":
            return True
        if not path.startswith("/api/discovery/solana/"):
            return False
        return path.endswith(("/jupiter-quote", "/jupiter-order", "/jupiter-execute"))

    async def __call__(self, scope: dict[str, object], receive: object, send: object) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope).encode("ascii")
        no_store = self._requires_no_store(str(scope.get("path") or ""))

        async def secure_send(message: dict[str, object]) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                if no_store:
                    headers = [
                        (key, value)
                        for key, value in headers
                        if bytes(key).lower() not in {b"cache-control", b"pragma", b"expires"}
                    ]
                headers.extend(
                    [
                        (b"content-security-policy", self._CSP.encode("ascii")),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"x-request-id", request_id),
                    ]
                )
                if no_store:
                    headers.extend(
                        [
                            (b"cache-control", b"no-store, max-age=0"),
                            (b"pragma", b"no-cache"),
                            (b"expires", b"0"),
                        ]
                    )
                if production_mode():
                    headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, secure_send)
