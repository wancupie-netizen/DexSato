from __future__ import annotations

import asyncio
from pathlib import Path

from application.production_security import (
    ApplicationBoundaryMiddleware,
    SecurityHeadersMiddleware,
    maximum_request_bytes,
)
from application.token_workspace_rate_limit import TokenWorkspaceRateLimitMiddleware


def _scope(path: str = "/", *, method: str = "GET", headers=None):
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
    }


def _run(app, scope, receive_messages=None):
    sent = []
    queue = list(receive_messages or [{"type": "http.request", "body": b"", "more_body": False}])

    async def receive():
        if queue:
            return queue.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent


def _start(sent):
    return next(message for message in sent if message["type"] == "http.response.start")


def _headers(start):
    return {bytes(key).lower(): bytes(value) for key, value in start.get("headers", [])}


def _status_app(status: int):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})
    return app


def test_tw_sec_010_security_headers_cover_common_statuses():
    for status in (200, 400, 404, 413, 429, 503):
        sent = _run(SecurityHeadersMiddleware(_status_app(status)), _scope())
        headers = _headers(_start(sent))
        assert headers[b"content-security-policy"]
        assert headers[b"permissions-policy"] == b"camera=(), microphone=(), geolocation=()"
        assert headers[b"referrer-policy"] == b"no-referrer"
        assert headers[b"x-content-type-options"] == b"nosniff"
        assert headers[b"x-frame-options"] == b"DENY"
        assert headers[b"x-request-id"]


def test_tw_sec_010_csp_removes_runtime_jsdelivr_but_preserves_inline_compatibility():
    csp = SecurityHeadersMiddleware._CSP
    assert "cdn.jsdelivr.net" not in csp
    assert "script-src 'self' 'unsafe-inline'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_tw_sec_010_wallet_balance_is_no_store():
    sent = _run(
        SecurityHeadersMiddleware(_status_app(200)),
        _scope("/api/discovery/solana/TokenAddress/wallet-balance"),
    )
    headers = _headers(_start(sent))
    assert headers[b"cache-control"] == b"no-store, max-age=0"
    assert headers[b"pragma"] == b"no-cache"
    assert headers[b"expires"] == b"0"


def test_tw_sec_010_public_market_feeds_do_not_gain_no_store():
    for endpoint in ("candles", "transactions"):
        sent = _run(
            SecurityHeadersMiddleware(_status_app(200)),
            _scope(f"/api/discovery/solana/TokenAddress/{endpoint}"),
        )
        headers = _headers(_start(sent))
        assert b"cache-control" not in headers


class _NeverLimiter:
    def __init__(self):
        self.calls = 0

    def check(self, checks):
        self.calls += 1
        raise AssertionError("Token Workspace limiter must not inspect an oversized request body")


async def _terminal(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _secured_boundary_stack(limiter):
    # Desired effective execution order:
    # SecurityHeaders -> ApplicationBoundary -> TokenWorkspaceRateLimit -> route
    return SecurityHeadersMiddleware(
        ApplicationBoundaryMiddleware(
            TokenWorkspaceRateLimitMiddleware(_terminal, limiter=limiter)
        )
    )


def test_tw_sec_010_content_length_oversize_rejected_before_token_body_parse():
    limiter = _NeverLimiter()
    limit = maximum_request_bytes()
    sent = _run(
        _secured_boundary_stack(limiter),
        _scope(
            "/api/discovery/solana/TokenAddress/jupiter-order",
            method="POST",
            headers=[(b"content-length", str(limit + 1).encode("ascii"))],
        ),
        [{"type": "http.request", "body": b"x" * 16, "more_body": False}],
    )
    start = _start(sent)
    assert start["status"] == 413
    assert limiter.calls == 0
    assert b"content-security-policy" in _headers(start)


def test_tw_sec_010_streaming_oversize_rejected_before_token_limiter_check():
    limiter = _NeverLimiter()
    limit = maximum_request_bytes()
    first = b"x" * min(limit, 1024)
    second = b"y" * (limit - len(first) + 1)
    sent = _run(
        _secured_boundary_stack(limiter),
        _scope(
            "/api/discovery/solana/TokenAddress/jupiter-execute",
            method="POST",
        ),
        [
            {"type": "http.request", "body": first, "more_body": True},
            {"type": "http.request", "body": second, "more_body": False},
        ],
    )
    start = _start(sent)
    assert start["status"] == 413
    assert limiter.calls == 0
    assert b"content-security-policy" in _headers(start)


def test_tw_sec_010_middleware_registration_preserves_effective_boundary_order():
    source = Path("app/main.py").read_text(encoding="utf-8")
    sequence = [
        "app.add_middleware(TokenWorkspaceRateLimitMiddleware)",
        "app.add_middleware(ApplicationBoundaryMiddleware)",
        "app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())",
        "app.add_middleware(ProductionLoggingMiddleware)",
        "app.add_middleware(SecurityHeadersMiddleware)",
    ]
    positions = [source.index(marker) for marker in sequence]
    assert positions == sorted(positions)


def test_tw_sec_010_self_hosted_solana_web3_runtime_remains_local():
    swap_js = Path("static/js/dexsato_solana_discovery_swap.js").read_text(encoding="utf-8")
    assert "/static/vendor/solana-web3/1.98.4/index.iife.min.js" in swap_js
    assert "cdn.jsdelivr.net" not in swap_js


def test_tw_sec_010_presenter_still_requires_inline_script_compatibility():
    presenter = Path("presentation/dexsato_solana_discovery_token_presenter.py").read_text(encoding="utf-8")
    assert presenter.count("<script>") >= 1
    assert "'unsafe-inline'" in SecurityHeadersMiddleware._CSP
