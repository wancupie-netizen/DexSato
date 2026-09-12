import asyncio
from application.production_security import SecurityHeadersMiddleware


def _run(status, path="/health/live"):
    async def downstream(scope, receive, send):
        await send({"type":"http.response.start","status":status,"headers":[]})
        await send({"type":"http.response.body","body":b""})
    sent=[]
    async def receive(): return {"type":"http.request","body":b"","more_body":False}
    async def send(message): sent.append(message)
    scope={"type":"http","method":"GET","path":path,"headers":[],"client":("127.0.0.1",1)}
    asyncio.run(SecurityHeadersMiddleware(downstream)(scope, receive, send))
    start=next(m for m in sent if m["type"]=="http.response.start")
    return {bytes(k).lower():bytes(v) for k,v in start["headers"]}


def test_security_headers_cover_full_gate_status_matrix():
    for status in (200,400,401,403,404,410,413,429,502,503):
        h=_run(status)
        for key in (b"content-security-policy",b"permissions-policy",b"referrer-policy",b"x-content-type-options",b"x-frame-options",b"x-request-id"):
            assert key in h


def test_sensitive_workspace_endpoints_are_no_store():
    paths=(
        "/api/discovery/solana/T/wallet-balance",
        "/api/discovery/solana/T/jupiter-quote",
        "/api/discovery/solana/T/jupiter-order",
        "/api/discovery/solana/T/jupiter-execute",
        "/content-control/login",
        "/telegram/send",
    )
    for path in paths:
        assert _run(200,path)[b"cache-control"] == b"no-store, max-age=0"
