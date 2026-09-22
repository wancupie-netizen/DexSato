import asyncio
import json

from application.token_workspace_rate_limit import (
    SlidingWindowRateLimiter,
    TokenWorkspaceRateLimitMiddleware,
    _checks_for_request,
)


class _App:
    def __init__(self):
        self.bodies = []

    async def __call__(self, scope, receive, send):
        message = await receive()
        self.bodies.append(message.get("body", b""))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})


async def _call(middleware, *, email):
    body = json.dumps({"email": email}).encode()
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/auth/otp/request",
        "headers": [],
        "client": ("192.0.2.10", 1234),
    }
    sent = []
    used = False

    async def receive():
        nonlocal used
        if used:
            return {"type": "http.disconnect"}
        used = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    await middleware(scope, receive, send)
    return next(item["status"] for item in sent if item["type"] == "http.response.start"), body


def test_otp_request_uses_ip_and_hashed_normalized_email_buckets():
    checks = _checks_for_request(
        method="POST",
        path="/auth/otp/request",
        ip="192.0.2.10",
        wallet=None,
        email="user@example.com",
    )
    assert len(checks) == 2
    assert all("user@example.com" not in key for key, _rule in checks)
    assert {rule.limit for _key, rule in checks} == {3, 10}
    assert all(rule.window_seconds == 900 for _key, rule in checks)


def test_otp_request_body_is_replayed_and_email_limit_is_enforced():
    app = _App()
    middleware = TokenWorkspaceRateLimitMiddleware(
        app,
        limiter=SlidingWindowRateLimiter(max_buckets=100),
    )
    for _ in range(3):
        status, body = asyncio.run(_call(middleware, email="User@Example.com"))
        assert status == 200
        assert app.bodies[-1] == body
    status, _body = asyncio.run(_call(middleware, email="user@example.com"))
    assert status == 429
    assert len(app.bodies) == 3

