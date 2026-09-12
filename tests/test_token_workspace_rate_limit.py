import asyncio
import json

from application.token_workspace_rate_limit import (
    SlidingWindowRateLimiter,
    TokenWorkspaceRateLimitMiddleware,
)


def _scope(path, *, method="GET", ip="10.0.0.1", headers=None):
    encoded = [
        (str(name).encode("latin-1"), str(value).encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": encoded,
        "client": (ip, 12345),
        "server": ("testserver", 80),
    }


async def _request(middleware, scope, body=b""):
    messages = []
    received = False

    async def receive():
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    return messages


def _status(messages):
    return next(m["status"] for m in messages if m["type"] == "http.response.start")


def _header(messages, name):
    start = next(m for m in messages if m["type"] == "http.response.start")
    wanted = name.lower().encode()
    for key, value in start["headers"]:
        if key.lower() == wanted:
            return value.decode()
    return None


class _App:
    def __init__(self):
        self.calls = 0
        self.bodies = []

    async def __call__(self, scope, receive, send):
        self.calls += 1
        body = b""
        if scope["method"] == "POST":
            message = await receive()
            body = message.get("body", b"")
            self.bodies.append(body)
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b"{}", "more_body": False})


def test_normal_candle_polling_allowed_then_flood_is_429():
    app = _App()
    middleware = TokenWorkspaceRateLimitMiddleware(app)

    for _ in range(12):
        assert _status(asyncio.run(_request(
            middleware,
            _scope("/api/discovery/solana/token-a/candles"),
        ))) == 200

    blocked = asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/token-a/candles"),
    ))
    assert _status(blocked) == 429
    assert int(_header(blocked, "retry-after")) >= 1
    assert app.calls == 12


def test_transaction_polling_has_independent_larger_allowance():
    app = _App()
    middleware = TokenWorkspaceRateLimitMiddleware(app)

    for _ in range(20):
        assert _status(asyncio.run(_request(
            middleware,
            _scope("/api/discovery/solana/token-a/transactions"),
        ))) == 200

    assert _status(asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/token-a/transactions"),
    ))) == 429
    assert app.calls == 20


def test_different_tokens_have_isolated_poll_buckets():
    app = _App()
    middleware = TokenWorkspaceRateLimitMiddleware(app)

    for _ in range(12):
        assert _status(asyncio.run(_request(
            middleware,
            _scope("/api/discovery/solana/token-a/candles"),
        ))) == 200

    assert _status(asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/token-b/candles"),
    ))) == 200


def test_spoofed_forwarded_for_does_not_bypass_peer_ip_limit():
    app = _App()
    middleware = TokenWorkspaceRateLimitMiddleware(app)

    for index in range(12):
        assert _status(asyncio.run(_request(
            middleware,
            _scope(
                "/api/discovery/solana/token-a/candles",
                headers={"x-forwarded-for": f"203.0.113.{index}"},
            ),
        ))) == 200

    blocked = asyncio.run(_request(
        middleware,
        _scope(
            "/api/discovery/solana/token-a/candles",
            headers={"x-forwarded-for": "198.51.100.50"},
        ),
    ))
    assert _status(blocked) == 429


def test_order_wallet_limit_blocks_before_app_and_body_is_replayed():
    app = _App()
    middleware = TokenWorkspaceRateLimitMiddleware(app)
    body = json.dumps(
        {
            "amount_sol": "0.01",
            "wallet_address": "Wallet111111111111111111111111111111111",
            "risk_acknowledged": True,
        }
    ).encode()

    for _ in range(4):
        messages = asyncio.run(_request(
            middleware,
            _scope(
                "/api/discovery/solana/token-a/jupiter-order",
                method="POST",
            ),
            body,
        ))
        assert _status(messages) == 200

    blocked = asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/token-a/jupiter-order", method="POST"),
        body,
    ))
    assert _status(blocked) == 429
    assert app.calls == 4
    assert app.bodies == [body] * 4


def test_execute_wallet_limit_is_separate_from_order():
    app = _App()
    middleware = TokenWorkspaceRateLimitMiddleware(app)
    body = json.dumps(
        {
            "request_id": "request-1",
            "wallet_address": "Wallet111111111111111111111111111111111",
            "signed_transaction": "AA==",
        }
    ).encode()

    for _ in range(4):
        assert _status(asyncio.run(_request(
            middleware,
            _scope("/api/discovery/solana/token-a/jupiter-execute", method="POST"),
            body,
        ))) == 200

    assert _status(asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/token-a/jupiter-execute", method="POST"),
        body,
    ))) == 429


def test_quote_is_ip_limited():
    app = _App()
    middleware = TokenWorkspaceRateLimitMiddleware(app)

    for _ in range(30):
        assert _status(asyncio.run(_request(
            middleware,
            _scope("/api/discovery/solana/token-a/jupiter-quote"),
        ))) == 200

    assert _status(asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/token-a/jupiter-quote"),
    ))) == 429


def test_limiter_capacity_is_bounded():
    app = _App()
    limiter = SlidingWindowRateLimiter(max_buckets=2)
    middleware = TokenWorkspaceRateLimitMiddleware(app, limiter=limiter)

    assert _status(asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/a/candles", ip="10.0.0.1"),
    ))) == 200
    assert _status(asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/b/candles", ip="10.0.0.2"),
    ))) == 200

    blocked = asyncio.run(_request(
        middleware,
        _scope("/api/discovery/solana/c/candles", ip="10.0.0.3"),
    ))
    assert _status(blocked) == 429
    assert limiter.bucket_count == 2
