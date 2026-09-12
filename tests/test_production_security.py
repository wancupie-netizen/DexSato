"""Security-boundary regression tests."""

import asyncio
import json
import logging
from unittest.mock import patch

from fastapi import HTTPException

from application.production_security import (
    ApplicationBoundaryMiddleware,
    ProductionLoggingMiddleware,
    SecurityHeadersMiddleware,
    _PRODUCTION_LOGGER,
    allowed_hosts,
    application_host,
    production_log_level,
    require_internal_access,
    safe_jupiter_error_detail,
    trusted_proxy_headers,
)

from application.token_workspace_rate_limit import (
    RULES,
    SlidingWindowRateLimiter,
    TokenWorkspaceRateLimitMiddleware,
)


class _Request:
    def __init__(self, authorization: str = "") -> None:
        self.headers = {"authorization": authorization}


def test_production_host_defaults_to_all_interfaces():
    with patch.dict("os.environ", {"DEXSATO_ENV": "production"}, clear=True):
        assert application_host() == "0.0.0.0"


def test_production_rejects_missing_or_wildcard_allowed_hosts():
    with patch.dict("os.environ", {"DEXSATO_ENV": "production"}, clear=True):
        try:
            allowed_hosts()
        except RuntimeError as error:
            assert "DEXSATO_ALLOWED_HOSTS" in str(error)
        else:
            raise AssertionError("Expected missing production hosts to fail")

    environment = {"DEXSATO_ENV": "production", "DEXSATO_ALLOWED_HOSTS": "*"}
    with patch.dict("os.environ", environment, clear=True):
        try:
            allowed_hosts()
        except RuntimeError as error:
            assert "Wildcard" in str(error)
        else:
            raise AssertionError("Expected wildcard production host to fail")


def test_proxy_headers_are_not_trusted_by_default():
    with patch.dict("os.environ", {}, clear=True):
        assert trusted_proxy_headers() is False


def test_debug_logging_is_rejected_in_production():
    environment = {"DEXSATO_ENV": "production", "DEXSATO_LOG_LEVEL": "DEBUG"}
    with patch.dict("os.environ", environment, clear=True):
        try:
            production_log_level()
        except RuntimeError as error:
            assert "DEBUG" in str(error)
        else:
            raise AssertionError("Expected production DEBUG logging to fail")


def test_only_reviewed_actionable_jupiter_error_is_public():
    actionable = RuntimeError(
        "Insufficient SOL balance. Reduce the swap amount or add SOL to your connected wallet."
    )
    provider_detail = RuntimeError("provider trace id=secret-upstream-detail")
    wallet_quota = RuntimeError(
        "This wallet has too many pending swap reviews. Complete or wait for an existing review to expire."
    )

    assert safe_jupiter_error_detail(actionable) == str(actionable)
    assert safe_jupiter_error_detail(wallet_quota) == str(wallet_quota)
    assert safe_jupiter_error_detail(provider_detail) == "Jupiter swap is temporarily unavailable."


def test_internal_routes_are_hidden_by_default_in_production():
    with patch.dict("os.environ", {"DEXSATO_ENV": "production"}, clear=True):
        try:
            require_internal_access(_Request())
        except HTTPException as error:
            assert error.status_code == 404
        else:
            raise AssertionError("Expected production internal route to be hidden")


def test_internal_route_accepts_matching_operator_bearer_token():
    token = "x" * 40
    environment = {
        "DEXSATO_ENV": "production",
        "DEXSATO_INTERNAL_ENDPOINTS_ENABLED": "true",
        "DEXSATO_OPERATOR_TOKEN": token,
    }
    with patch.dict("os.environ", environment, clear=True):
        assert require_internal_access(_Request(f"Bearer {token}")) is None


def test_boundary_rejects_oversized_content_length_before_application():
    called = False

    async def downstream(scope, receive, send):
        nonlocal called
        called = True

    middleware = ApplicationBoundaryMiddleware(downstream)
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "path": "/api/example",
        "client": ("127.0.0.1", 1234),
        "headers": [(b"content-length", b"20000")],
    }
    asyncio.run(middleware(scope, receive, send))

    assert called is False
    assert sent[0]["status"] == 413


def test_shared_limiter_rate_limits_sensitive_route():
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = TokenWorkspaceRateLimitMiddleware(
        downstream,
        limiter=SlidingWindowRateLimiter(max_buckets=100),
    )

    async def one_request():
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/telegram/send",
            "client": ("127.0.0.1", 1234),
            "headers": [],
        }
        await middleware(scope, receive, send)
        return sent[0]["status"]

    statuses = asyncio.run(_run_many(one_request, 4))
    assert statuses == [200, 200, 200, 429]


def test_shared_in_memory_limiter_sweeps_stale_buckets_and_bounds_new_clients():
    current = [1.0]
    limiter = SlidingWindowRateLimiter(max_buckets=2, clock=lambda: current[0])
    rule = RULES["workspace"]

    assert limiter.check([("client-a", rule)]).allowed is True
    assert limiter.check([("client-b", rule)]).allowed is True
    assert limiter.check([("client-c", rule)]).allowed is False
    assert limiter.bucket_count == 2

    current[0] = 902.0
    assert limiter.check([("client-c", rule)]).allowed is True
    assert limiter.bucket_count == 1


def test_security_headers_are_attached_without_echoing_request_id():
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = SecurityHeadersMiddleware(downstream)
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health/live",
        "client": ("127.0.0.1", 1234),
        "headers": [(b"x-request-id", b"attacker-controlled")],
    }
    asyncio.run(middleware(scope, receive, send))

    headers = dict(sent[0]["headers"])
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert headers[b"x-frame-options"] == b"DENY"
    assert headers[b"referrer-policy"] == b"no-referrer"
    assert b"frame-ancestors 'none'" in headers[b"content-security-policy"]
    assert headers[b"x-request-id"] != b"attacker-controlled"
    assert b"cache-control" not in headers


def test_sensitive_jupiter_and_operator_responses_are_never_cached():
    async def downstream(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"cache-control", b"public, max-age=3600")],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    async def headers_for(path):
        middleware = SecurityHeadersMiddleware(downstream)
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {"type": "http", "method": "POST", "path": path, "headers": []}
        await middleware(scope, receive, send)
        return dict(sent[0]["headers"])

    paths = [
        "/api/discovery/solana/Mint111/jupiter-quote",
        "/api/discovery/solana/Mint111/jupiter-order",
        "/api/discovery/solana/Mint111/jupiter-execute",
        "/content-control/login",
        "/content-control/generate",
        "/telegram/send",
    ]
    for path in paths:
        headers = asyncio.run(headers_for(path))
        assert headers[b"cache-control"] == b"no-store, max-age=0"
        assert headers[b"pragma"] == b"no-cache"
        assert headers[b"expires"] == b"0"


def test_production_logging_uses_sanitized_route_and_excludes_request_contents():
    token = "SensitiveMint111111111111111111111111111"
    signed = "signed-transaction-secret"

    async def downstream(scope, receive, send):
        await receive()
        await send({"type": "http.response.start", "status": 400, "headers": []})
        await send({"type": "http.response.body", "body": b"rejected"})

    middleware = ProductionLoggingMiddleware(downstream)
    sent = []

    async def receive():
        return {"type": "http.request", "body": signed.encode(), "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": f"/api/discovery/solana/{token}/jupiter-execute",
        "query_string": b"wallet=private-wallet-value",
        "headers": [(b"authorization", b"Bearer private-api-key")],
    }
    with patch.object(_PRODUCTION_LOGGER, "log") as emit:
        asyncio.run(middleware(scope, receive, send))

    level, raw = emit.call_args.args
    payload = json.loads(raw)
    assert level == logging.WARNING
    assert payload["route"] == "/api/discovery/solana/:token/jupiter-execute"
    assert payload["event"] == "http_request_rejected"
    assert payload["status"] == 400
    assert isinstance(payload["timestamp_unix_ms"], int)
    assert token not in raw
    assert signed not in raw
    assert "private-wallet-value" not in raw
    assert "private-api-key" not in raw


def test_production_exception_log_exposes_type_not_exception_message():
    async def downstream(scope, receive, send):
        raise RuntimeError("upstream-secret-and-wallet-value")

    middleware = ProductionLoggingMiddleware(downstream)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        return None

    scope = {"type": "http", "method": "GET", "path": "/health/ready", "headers": []}
    with patch.object(_PRODUCTION_LOGGER, "log") as emit:
        try:
            asyncio.run(middleware(scope, receive, send))
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected downstream exception")

    raw = emit.call_args.args[1]
    payload = json.loads(raw)
    assert payload["event"] == "http_exception"
    assert payload["exception_type"] == "RuntimeError"
    assert "upstream-secret-and-wallet-value" not in raw


async def _run_many(operation, count):
    results = []
    for _ in range(count):
        results.append(await operation())
    return results
