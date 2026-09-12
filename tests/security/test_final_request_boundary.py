import asyncio

from application.production_security import ApplicationBoundaryMiddleware, maximum_request_bytes


def _scope(*, headers=None, path="/api/discovery/solana/T/jupiter-order"):
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": headers or [],
        "client": ("127.0.0.1", 1234),
    }


def _run(app, scope, messages):
    sent = []
    queue = list(messages)
    async def receive():
        if queue:
            return queue.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message): sent.append(message)
    asyncio.run(app(scope, receive, send))
    return sent


def _status(sent):
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def test_invalid_content_length_is_400_before_downstream():
    called = False
    async def downstream(scope, receive, send):
        nonlocal called
        called = True
    app = ApplicationBoundaryMiddleware(downstream)
    sent = _run(app, _scope(headers=[(b"content-length", b"not-a-number")]), [])
    assert _status(sent) == 400
    assert called is False


def test_chunked_oversize_is_413_before_downstream_finishes_body():
    limit = maximum_request_bytes()
    consumed = []
    async def downstream(scope, receive, send):
        while True:
            message = await receive()
            consumed.append(len(message.get("body", b"")))
            if not message.get("more_body", False):
                break
        await send({"type":"http.response.start","status":200,"headers":[]})
        await send({"type":"http.response.body","body":b""})
    app = ApplicationBoundaryMiddleware(downstream)
    sent = _run(app, _scope(), [
        {"type":"http.request","body":b"a" * min(1024, limit),"more_body":True},
        {"type":"http.request","body":b"b" * (limit + 1),"more_body":False},
    ])
    assert _status(sent) == 413
    assert consumed
