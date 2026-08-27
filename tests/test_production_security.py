"""Security-boundary regression tests."""

import asyncio
from unittest.mock import patch

from fastapi import HTTPException

from application.production_security import (
    ApplicationBoundaryMiddleware,
    SecurityHeadersMiddleware,
    allowed_hosts,
    application_host,
    require_internal_access,
    safe_jupiter_error_detail,
    trusted_proxy_headers,
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


def test_only_reviewed_actionable_jupiter_error_is_public():
    actionable = RuntimeError(
        "Insufficient SOL balance. Reduce the swap amount or add SOL to your connected wallet."
    )
    provider_detail = RuntimeError("provider trace id=secret-upstream-detail")

    assert safe_jupiter_error_detail(actionable) == str(actionable)
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


def test_boundary_rate_limits_sensitive_route():
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = ApplicationBoundaryMiddleware(downstream)

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


async def _run_many(operation, count):
    results = []
    for _ in range(count):
        results.append(await operation())
    return results
