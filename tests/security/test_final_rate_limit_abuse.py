import asyncio

from application.token_workspace_rate_limit import (
    RateLimitStoreUnavailable,
    RedisSlidingWindowRateLimiter,
    RULES,
    TokenWorkspaceRateLimitMiddleware,
    _checks_for_request,
)


class _BadRedis:
    def eval(self, *args, **kwargs):
        raise RuntimeError("redis-secret://must-not-leak")


class _App:
    def __init__(self): self.calls = 0
    async def __call__(self, scope, receive, send):
        self.calls += 1
        await send({"type":"http.response.start","status":200,"headers":[]})
        await send({"type":"http.response.body","body":b"ok"})


def _scope(path, method="GET"):
    return {"type":"http","method":method,"path":path,"headers":[],"client":("203.0.113.9",1234)}


def test_redis_operation_failure_fails_closed_before_route():
    app = _App()
    limiter = RedisSlidingWindowRateLimiter(_BadRedis())
    middleware = TokenWorkspaceRateLimitMiddleware(app, limiter=limiter)
    sent=[]
    async def receive(): return {"type":"http.request","body":b"","more_body":False}
    async def send(message): sent.append(message)
    asyncio.run(middleware(_scope("/discovery/solana/TokenA"), receive, send))
    start=next(m for m in sent if m["type"]=="http.response.start")
    body=next(m for m in sent if m["type"]=="http.response.body")["body"]
    assert start["status"] == 503
    assert app.calls == 0
    assert b"redis-secret" not in body


def test_specific_routes_do_not_double_consume_generic_fallback():
    candles = _checks_for_request(method="GET", path="/api/discovery/solana/T/candles", ip="1.2.3.4", wallet=None)
    txs = _checks_for_request(method="GET", path="/api/discovery/solana/T/transactions", ip="1.2.3.4", wallet=None)
    assert [rule.name for _, rule in candles] == ["candles"]
    assert [rule.name for _, rule in txs] == ["transactions"]


def test_locked_jupiter_limits_remain_exact():
    assert RULES["jupiter-order-ip"].limit == 6
    assert RULES["jupiter-order-wallet"].limit == 4
    assert RULES["jupiter-order-global"].limit == 60
    assert RULES["jupiter-execute-ip"].limit == 6
    assert RULES["jupiter-execute-wallet"].limit == 4
    assert RULES["jupiter-execute-global"].limit == 60
