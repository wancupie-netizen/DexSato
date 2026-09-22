"""Shared rate limiting for DexSato public and operator-facing HTTP routes.

Production uses one Redis-backed atomic sliding-window store across all replicas.
Local development and tests may explicitly use the bounded in-memory store.
Client identity defaults to the ASGI peer address. Forwarded client identity is
accepted only when trusted proxy handling is explicitly enabled.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import math
import os
import re
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from application.production_security import trusted_proxy_headers


MAX_BUCKETS = 10_000
WINDOW_SECONDS = 60.0
REDIS_PREFIX = "dexsato:ratelimit"
MAX_FORWARDED_FOR_BYTES = 1024
MAX_FORWARDED_FOR_HOPS = 16

_TOKEN_WORKSPACE_ROUTE = re.compile(r"^/discovery/solana/([^/]+)$")
_API_ROUTE = re.compile(
    r"^/api/discovery/solana/([^/]+)/(candles|transactions|jupiter-quote|jupiter-order|jupiter-execute)$"
)


class RateLimitStoreUnavailable(RuntimeError):
    """Raised when the shared production limiter cannot safely evaluate a request."""


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: float = WINDOW_SECONDS


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0
    rule: str | None = None


@dataclass
class _Bucket:
    events: deque[float]
    last_seen: float
    max_window: float


class SlidingWindowRateLimiter:
    """Concurrency-safe bounded in-memory store for local development and tests."""

    def __init__(
        self,
        *,
        max_buckets: int = MAX_BUCKETS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_buckets < 1:
            raise ValueError("max_buckets must be positive")
        self.max_buckets = max_buckets
        self.clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[str, _Bucket] = {}

    def _prune_bucket(self, bucket: _Bucket, now: float, window: float) -> None:
        cutoff = now - window
        while bucket.events and bucket.events[0] <= cutoff:
            bucket.events.popleft()

    def _prune_expired_buckets(self, now: float) -> None:
        stale = [
            key
            for key, bucket in self._buckets.items()
            if not bucket.events or now - bucket.last_seen >= bucket.max_window
        ]
        for key in stale:
            self._buckets.pop(key, None)

    def check(self, checks: list[tuple[str, RateLimitRule]]) -> RateLimitDecision:
        """Atomically evaluate all keys and consume one event only if all pass."""
        if not checks:
            return RateLimitDecision(True)

        now = self.clock()
        with self._lock:
            self._prune_expired_buckets(now)

            prepared: list[tuple[str, RateLimitRule, _Bucket | None]] = []
            new_keys = 0
            for key, rule in checks:
                bucket = self._buckets.get(key)
                if bucket is None:
                    new_keys += 1
                else:
                    self._prune_bucket(bucket, now, rule.window_seconds)
                    if len(bucket.events) >= rule.limit:
                        retry = max(
                            1,
                            int(math.ceil(rule.window_seconds - (now - bucket.events[0]))),
                        )
                        bucket.last_seen = now
                        bucket.max_window = max(bucket.max_window, rule.window_seconds)
                        return RateLimitDecision(False, retry, rule.name)
                prepared.append((key, rule, bucket))

            if len(self._buckets) + new_keys > self.max_buckets:
                return RateLimitDecision(False, int(WINDOW_SECONDS), "limiter_capacity")

            for key, rule, bucket in prepared:
                if bucket is None:
                    bucket = _Bucket(deque(), now, rule.window_seconds)
                    self._buckets[key] = bucket
                bucket.events.append(now)
                bucket.last_seen = now
                bucket.max_window = max(bucket.max_window, rule.window_seconds)

        return RateLimitDecision(True)

    @property
    def bucket_count(self) -> int:
        with self._lock:
            return len(self._buckets)


_REDIS_CHECK_LUA = r"""
local clock = redis.call('TIME')
local now_ms = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local rule_count = #KEYS

for i = 1, rule_count do
    local base = (i - 1) * 3
    local limit = tonumber(ARGV[base + 1])
    local window_ms = tonumber(ARGV[base + 2])
    local rule_name = ARGV[base + 3]
    local cutoff = now_ms - window_ms

    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', cutoff)
    local count = redis.call('ZCARD', KEYS[i])
    if count >= limit then
        local oldest = redis.call('ZRANGE', KEYS[i], 0, 0, 'WITHSCORES')
        local retry_ms = window_ms
        if oldest[2] then
            retry_ms = math.max(1, tonumber(oldest[2]) + window_ms - now_ms)
        end
        return {0, math.max(1, math.ceil(retry_ms / 1000)), rule_name}
    end
end

local nonce = ARGV[rule_count * 3 + 1]
local member = tostring(now_ms) .. ':' .. nonce
for i = 1, rule_count do
    local base = (i - 1) * 3
    local window_ms = tonumber(ARGV[base + 2])
    redis.call('ZADD', KEYS[i], now_ms, member)
    redis.call('PEXPIRE', KEYS[i], window_ms + 5000)
end

return {1, 0, ''}
"""


class RedisSlidingWindowRateLimiter:
    """Deployment-wide atomic sliding-window limiter backed by Redis."""

    def __init__(self, client: Any, *, prefix: str = REDIS_PREFIX) -> None:
        self.client = client
        self.prefix = prefix

    @classmethod
    def from_url(cls, url: str, *, prefix: str = REDIS_PREFIX) -> "RedisSlidingWindowRateLimiter":
        try:
            import redis
            client = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
                health_check_interval=30,
            )
        except Exception as error:
            raise RateLimitStoreUnavailable("Redis rate-limit store could not be configured.") from error
        return cls(client, prefix=prefix)

    def ping(self) -> None:
        try:
            if self.client.ping() is not True:
                raise RateLimitStoreUnavailable("Redis rate-limit health check failed.")
        except RateLimitStoreUnavailable:
            raise
        except Exception as error:
            raise RateLimitStoreUnavailable("Redis rate-limit store is unavailable.") from error

    def _redis_key(self, logical_key: str) -> str:
        digest = hashlib.sha256(logical_key.encode("utf-8")).hexdigest()
        rule = logical_key.split(":", 1)[0]
        return f"{self.prefix}:{rule}:{digest}"

    def check(self, checks: list[tuple[str, RateLimitRule]]) -> RateLimitDecision:
        if not checks:
            return RateLimitDecision(True)

        keys = [self._redis_key(key) for key, _rule in checks]
        args: list[Any] = []
        for _key, rule in checks:
            args.extend([int(rule.limit), int(math.ceil(rule.window_seconds * 1000)), rule.name])
        args.append(secrets.token_hex(12))

        try:
            result = self.client.eval(_REDIS_CHECK_LUA, len(keys), *keys, *args)
        except Exception as error:
            raise RateLimitStoreUnavailable("Redis rate-limit operation failed.") from error

        if not isinstance(result, (list, tuple)) or len(result) < 3:
            raise RateLimitStoreUnavailable("Redis rate-limit operation returned an invalid result.")
        try:
            allowed = int(result[0]) == 1
            retry_after = int(result[1])
            rule_name = str(result[2] or "") or None
        except (TypeError, ValueError) as error:
            raise RateLimitStoreUnavailable("Redis rate-limit operation returned an invalid result.") from error
        return RateLimitDecision(allowed, max(0, retry_after), rule_name)


RULES = {
    "workspace": RateLimitRule("workspace", 60),
    "candles": RateLimitRule("candles", 12),
    "transactions": RateLimitRule("transactions", 20),
    "jupiter-quote-ip": RateLimitRule("jupiter-quote-ip", 30),
    "jupiter-order-ip": RateLimitRule("jupiter-order-ip", 6),
    "jupiter-order-wallet": RateLimitRule("jupiter-order-wallet", 4),
    "jupiter-order-global": RateLimitRule("jupiter-order-global", 60),
    "jupiter-execute-ip": RateLimitRule("jupiter-execute-ip", 6),
    "jupiter-execute-wallet": RateLimitRule("jupiter-execute-wallet", 4),
    "jupiter-execute-global": RateLimitRule("jupiter-execute-global", 60),
    "content-login": RateLimitRule("content-login", 5, 900),
    "product-otp-request-ip": RateLimitRule("product-otp-request-ip", 10, 900),
    "product-otp-request-email": RateLimitRule("product-otp-request-email", 3, 900),
    "product-otp-verify-ip": RateLimitRule("product-otp-verify-ip", 10, 900),
    "product-otp-verify-email": RateLimitRule("product-otp-verify-email", 5, 900),
    "content-generate": RateLimitRule("content-generate", 20),
    "telegram-send": RateLimitRule("telegram-send", 3),
    "solana-api": RateLimitRule("solana-api", 90),
    "general-api": RateLimitRule("general-api", 120),
}


_configured_limiter: SlidingWindowRateLimiter | RedisSlidingWindowRateLimiter | None = None
_configured_limiter_lock = threading.RLock()


def _memory_bucket_limit() -> int:
    raw = os.getenv("DEXSATO_RATE_LIMIT_MAX_BUCKETS", str(MAX_BUCKETS)).strip()
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError("DEXSATO_RATE_LIMIT_MAX_BUCKETS must be an integer.") from error
    if value < 1 or value > 100_000:
        raise RuntimeError("DEXSATO_RATE_LIMIT_MAX_BUCKETS must be between 1 and 100000.")
    return value


def _rate_limit_store_mode() -> str:
    value = os.getenv("DEXSATO_RATE_LIMIT_STORE", "memory").strip().lower()
    if value not in {"memory", "redis"}:
        raise RuntimeError("DEXSATO_RATE_LIMIT_STORE must be memory or redis.")
    return value


def configure_rate_limit_store() -> None:
    global _configured_limiter
    mode = _rate_limit_store_mode()
    production = os.getenv("DEXSATO_ENV", "development").strip().lower() == "production"
    if production and mode != "redis":
        raise RuntimeError("Production requires DEXSATO_RATE_LIMIT_STORE=redis.")

    with _configured_limiter_lock:
        if mode == "redis":
            url = os.getenv("REDIS_URL", "").strip()
            if not url:
                raise RateLimitStoreUnavailable("REDIS_URL is required for the Redis rate-limit store.")
            limiter = RedisSlidingWindowRateLimiter.from_url(url)
            limiter.ping()
            _configured_limiter = limiter
        else:
            _configured_limiter = SlidingWindowRateLimiter(max_buckets=_memory_bucket_limit())


def _default_limiter() -> SlidingWindowRateLimiter | RedisSlidingWindowRateLimiter:
    with _configured_limiter_lock:
        if _configured_limiter is not None:
            return _configured_limiter
    return SlidingWindowRateLimiter(max_buckets=_memory_bucket_limit())


def _hash_identity(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _peer_ip(scope: dict[str, Any]) -> str:
    """Return the direct ASGI peer identity."""
    client = scope.get("client")
    if isinstance(client, (tuple, list)) and client:
        value = str(client[0] or "").strip()
        if value:
            return value
    return "unknown"


def _forwarded_for_ip(scope: dict[str, Any]) -> str | None:
    """Return a validated right-most X-Forwarded-For address.

    This is used only when trusted proxy handling is explicitly enabled.
    Ambiguous, oversized, malformed, or excessively deep forwarding chains
    are rejected so the caller can safely fall back to the ASGI peer.
    """
    headers = scope.get("headers")
    if not isinstance(headers, (tuple, list)):
        return None

    forwarded_values: list[bytes] = []
    for item in headers:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            continue
        key, value = item
        try:
            name = bytes(key).lower()
            raw_value = bytes(value)
        except (TypeError, ValueError):
            continue
        if name == b"x-forwarded-for":
            forwarded_values.append(raw_value)

    if len(forwarded_values) != 1:
        return None

    raw = forwarded_values[0]
    if not raw or len(raw) > MAX_FORWARDED_FOR_BYTES:
        return None

    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return None

    hops = [part.strip() for part in text.split(",")]
    if (
        not hops
        or len(hops) > MAX_FORWARDED_FOR_HOPS
        or any(not hop for hop in hops)
    ):
        return None

    candidate = hops[-1]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _client_ip(scope: dict[str, Any]) -> str:
    """Resolve client identity without trusting proxy headers by default."""
    if trusted_proxy_headers():
        forwarded = _forwarded_for_ip(scope)
        if forwarded is not None:
            return forwarded
    return _peer_ip(scope)


async def _read_body(receive: Callable[..., Any]) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message.get("type") != "http.request":
            continue
        body = message.get("body", b"")
        if body:
            chunks.append(body)
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _wallet_from_json(body: bytes) -> str | None:
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = str(payload.get("wallet_address") or "").strip()
    return value or None


def _email_from_json(body: bytes) -> str | None:
    if not body:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = str(payload.get("email") or "").strip().casefold()
    if not value or len(value) > 254:
        return None
    return value


def _checks_for_request(
    *,
    method: str,
    path: str,
    ip: str,
    wallet: str | None,
    email: str | None = None,
) -> list[tuple[str, RateLimitRule]]:
    ip_key = _hash_identity(ip)

    if path == "/auth/otp/request" and method == "POST":
        checks = [(f"product-otp-request:ip:{ip_key}", RULES["product-otp-request-ip"])]
        if email:
            checks.append(
                (f"product-otp-request:email:{_hash_identity(email)}", RULES["product-otp-request-email"])
            )
        return checks
    if path == "/auth/otp/verify" and method == "POST":
        checks = [(f"product-otp-verify:ip:{ip_key}", RULES["product-otp-verify-ip"])]
        if email:
            checks.append(
                (f"product-otp-verify:email:{_hash_identity(email)}", RULES["product-otp-verify-email"])
            )
        return checks
    if path == "/content-control/login" and method == "POST":
        return [(f"content-login:ip:{ip_key}", RULES["content-login"])]
    if path == "/content-control/generate" and method == "POST":
        return [(f"content-generate:ip:{ip_key}", RULES["content-generate"])]
    if path == "/telegram/send" and method == "POST":
        return [(f"telegram-send:ip:{ip_key}", RULES["telegram-send"])]

    workspace = _TOKEN_WORKSPACE_ROUTE.fullmatch(path)
    if workspace and method == "GET":
        return [(f"workspace:ip:{ip_key}", RULES["workspace"])]

    matched = _API_ROUTE.fullmatch(path)
    if matched:
        token, endpoint = matched.groups()
        token_key = _hash_identity(token)
        if endpoint == "candles" and method == "GET":
            return [(f"candles:ip:{ip_key}:token:{token_key}", RULES["candles"])]
        if endpoint == "transactions" and method == "GET":
            return [(f"transactions:ip:{ip_key}:token:{token_key}", RULES["transactions"])]
        if endpoint == "jupiter-quote" and method == "GET":
            return [(f"jupiter-quote:ip:{ip_key}", RULES["jupiter-quote-ip"])]
        if endpoint == "jupiter-order" and method == "POST":
            checks = [
                (f"jupiter-order:ip:{ip_key}", RULES["jupiter-order-ip"]),
                ("jupiter-order:global", RULES["jupiter-order-global"]),
            ]
            if wallet:
                checks.append((f"jupiter-order:wallet:{_hash_identity(wallet)}", RULES["jupiter-order-wallet"]))
            return checks
        if endpoint == "jupiter-execute" and method == "POST":
            checks = [
                (f"jupiter-execute:ip:{ip_key}", RULES["jupiter-execute-ip"]),
                ("jupiter-execute:global", RULES["jupiter-execute-global"]),
            ]
            if wallet:
                checks.append((f"jupiter-execute:wallet:{_hash_identity(wallet)}", RULES["jupiter-execute-wallet"]))
            return checks

    if path.startswith("/api/discovery/solana/"):
        return [(f"solana-api:ip:{ip_key}", RULES["solana-api"])]
    if path.startswith("/api/"):
        return [(f"general-api:ip:{ip_key}", RULES["general-api"])]
    return []


async def _send_json(send, *, status: int, detail: str, extra_headers=None) -> None:
    body = json.dumps({"detail": detail}, separators=(",", ":")).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"cache-control", b"no-store"),
    ]
    headers.extend(extra_headers or [])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body, "more_body": False})


async def _send_429(send, decision: RateLimitDecision) -> None:
    await _send_json(
        send,
        status=429,
        detail="Too many requests. Please retry shortly.",
        extra_headers=[(b"retry-after", str(max(1, decision.retry_after)).encode("ascii"))],
    )


async def _send_503(send) -> None:
    await _send_json(send, status=503, detail="Request protection is temporarily unavailable.")


class TokenWorkspaceRateLimitMiddleware:
    """Apply the consolidated shared rate policy before route/provider work starts."""

    def __init__(self, app, *, limiter=None) -> None:
        self.app = app
        self.limiter = limiter or _default_limiter()

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "").upper()
        path = str(scope.get("path") or "")
        body = None
        wallet = None
        email = None

        inspect_json_body = method == "POST" and (
            path.endswith("/jupiter-order")
            or path.endswith("/jupiter-execute")
            or path in {"/auth/otp/request", "/auth/otp/verify"}
        )
        if inspect_json_body:
            body = await _read_body(receive)
            wallet = _wallet_from_json(body)
            email = _email_from_json(body)

        checks = _checks_for_request(
            method=method,
            path=path,
            ip=_client_ip(scope),
            wallet=wallet,
            email=email,
        )
        if checks:
            try:
                if isinstance(self.limiter, RedisSlidingWindowRateLimiter):
                    decision = await asyncio.to_thread(self.limiter.check, checks)
                else:
                    decision = self.limiter.check(checks)
            except RateLimitStoreUnavailable:
                await _send_503(send)
                return
            if not decision.allowed:
                await _send_429(send, decision)
                return

        if body is None:
            await self.app(scope, receive, send)
            return

        replayed = False

        async def replay_receive():
            nonlocal replayed
            if replayed:
                await asyncio.sleep(0)
                return {"type": "http.request", "body": b"", "more_body": False}
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)


SharedRateLimitMiddleware = TokenWorkspaceRateLimitMiddleware
