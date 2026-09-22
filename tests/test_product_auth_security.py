import asyncio

from application.production_security import SecurityHeadersMiddleware, _safe_route


def test_product_auth_routes_have_fixed_safe_log_classification():
    for path in ("/login", "/logout", "/auth/otp/request", "/auth/otp/verify"):
        assert _safe_route(path) == path


def test_product_auth_responses_are_never_cached():
    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [(b"cache-control", b"public")]})
        await send({"type": "http.response.body", "body": b"ok"})

    async def headers_for(path):
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        await SecurityHeadersMiddleware(downstream)(
            {"type": "http", "method": "POST", "path": path, "headers": []},
            receive,
            send,
        )
        return dict(sent[0]["headers"])

    for path in ("/login", "/logout", "/auth/otp/request", "/auth/otp/verify"):
        headers = asyncio.run(headers_for(path))
        assert headers[b"cache-control"] == b"no-store, max-age=0"
        assert headers[b"pragma"] == b"no-cache"

