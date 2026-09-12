import pytest

from application.token_workspace_rate_limit import (
    RedisSlidingWindowRateLimiter,
    RateLimitStoreUnavailable,
    RULES,
    _REDIS_CHECK_LUA,
    _checks_for_request,
)


class FakeRedis:
    def __init__(self):
        self.events = {}
        self.now_ms = 1_000_000
        self.fail = False

    def ping(self):
        if self.fail:
            raise RuntimeError("down")
        return True

    def eval(self, script, key_count, *items):
        if self.fail:
            raise RuntimeError("down")
        assert script == _REDIS_CHECK_LUA
        keys = list(items[:key_count])
        args = list(items[key_count:])
        checks = []
        for index, key in enumerate(keys):
            base = index * 3
            limit = int(args[base])
            window_ms = int(args[base + 1])
            rule_name = str(args[base + 2])
            bucket = list(self.events.get(key, []))
            cutoff = self.now_ms - window_ms
            bucket = [stamp for stamp in bucket if stamp > cutoff]
            checks.append((key, bucket, limit, window_ms, rule_name))
        for key, bucket, limit, window_ms, rule_name in checks:
            if len(bucket) >= limit:
                retry = max(1, (bucket[0] + window_ms - self.now_ms + 999) // 1000)
                return [0, retry, rule_name]
        for key, bucket, limit, window_ms, rule_name in checks:
            bucket.append(self.now_ms)
            self.events[key] = bucket
        return [1, 0, ""]


def test_tw_sec_011_two_clients_share_one_redis_limit():
    shared = FakeRedis()
    first = RedisSlidingWindowRateLimiter(shared)
    second = RedisSlidingWindowRateLimiter(shared)
    checks = [("jupiter-order:ip:abc", RULES["jupiter-order-ip"])]
    for _ in range(3):
        assert first.check(checks).allowed
        assert second.check(checks).allowed
    blocked = first.check(checks)
    assert blocked.allowed is False
    assert blocked.rule == "jupiter-order-ip"


def test_tw_sec_011_multi_rule_rejection_is_atomic():
    shared = FakeRedis()
    limiter = RedisSlidingWindowRateLimiter(shared)
    wallet = ("jupiter-order:wallet:def", RULES["jupiter-order-wallet"])
    for _ in range(4):
        assert limiter.check([wallet]).allowed
    before = {key: len(value) for key, value in shared.events.items()}
    decision = limiter.check([
        ("jupiter-order:ip:abc", RULES["jupiter-order-ip"]),
        wallet,
        ("jupiter-order:global", RULES["jupiter-order-global"]),
    ])
    after = {key: len(value) for key, value in shared.events.items()}
    assert decision.allowed is False
    assert decision.rule == "jupiter-order-wallet"
    assert after == before


def test_tw_sec_011_raw_identifiers_are_not_in_logical_keys():
    checks = _checks_for_request(
        method="POST",
        path="/api/discovery/solana/TokenSecret/jupiter-order",
        ip="203.0.113.10",
        wallet="WalletSecret",
    )
    joined = " ".join(key for key, _rule in checks)
    assert "203.0.113.10" not in joined
    assert "WalletSecret" not in joined
    assert "TokenSecret" not in joined


def test_tw_sec_011_locked_tw002_limits_preserved():
    assert RULES["workspace"].limit == 60
    assert RULES["candles"].limit == 12
    assert RULES["transactions"].limit == 20
    assert RULES["jupiter-quote-ip"].limit == 30
    assert RULES["jupiter-order-ip"].limit == 6
    assert RULES["jupiter-order-wallet"].limit == 4
    assert RULES["jupiter-order-global"].limit == 60
    assert RULES["jupiter-execute-ip"].limit == 6
    assert RULES["jupiter-execute-wallet"].limit == 4
    assert RULES["jupiter-execute-global"].limit == 60


def test_tw_sec_011_legacy_boundary_limits_consolidated():
    assert RULES["content-login"].limit == 5
    assert RULES["content-login"].window_seconds == 900
    assert RULES["content-generate"].limit == 20
    assert RULES["telegram-send"].limit == 3
    assert RULES["solana-api"].limit == 90
    assert RULES["general-api"].limit == 120


def test_tw_sec_011_redis_failure_fails_closed():
    shared = FakeRedis()
    shared.fail = True
    limiter = RedisSlidingWindowRateLimiter(shared)
    with pytest.raises(RateLimitStoreUnavailable):
        limiter.check([("workspace:ip:abc", RULES["workspace"])])


def test_tw_sec_011_lua_checks_before_any_consume():
    assert "ZREMRANGEBYSCORE" in _REDIS_CHECK_LUA
    assert "ZCARD" in _REDIS_CHECK_LUA
    assert "ZADD" in _REDIS_CHECK_LUA
    assert "PEXPIRE" in _REDIS_CHECK_LUA
    assert _REDIS_CHECK_LUA.index("return {0") < _REDIS_CHECK_LUA.index("ZADD")


def test_tw_sec_011_production_rejects_memory_store(monkeypatch):
    import application.token_workspace_rate_limit as module
    monkeypatch.setenv("DEXSATO_ENV", "production")
    monkeypatch.setenv("DEXSATO_RATE_LIMIT_STORE", "memory")
    with pytest.raises(RuntimeError, match="DEXSATO_RATE_LIMIT_STORE=redis"):
        module.configure_rate_limit_store()

def test_tw_sec_011_specific_routes_do_not_double_consume_generic_buckets():
    candles = _checks_for_request(
        method="GET",
        path="/api/discovery/solana/TokenA/candles",
        ip="203.0.113.1",
        wallet=None,
    )
    transactions = _checks_for_request(
        method="GET",
        path="/api/discovery/solana/TokenA/transactions",
        ip="203.0.113.1",
        wallet=None,
    )
    fallback = _checks_for_request(
        method="GET",
        path="/api/discovery/solana/TokenA/wallet-balance",
        ip="203.0.113.1",
        wallet=None,
    )

    assert [rule.name for _key, rule in candles] == ["candles"]
    assert [rule.name for _key, rule in transactions] == ["transactions"]
    assert [rule.name for _key, rule in fallback] == ["solana-api"]

