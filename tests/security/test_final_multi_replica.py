from application.token_workspace_rate_limit import RedisSlidingWindowRateLimiter, RULES, _REDIS_CHECK_LUA


class _SharedRedis:
    def __init__(self):
        self.events={}
        self.now_ms=1_000_000
    def eval(self, script, key_count, *items):
        assert script == _REDIS_CHECK_LUA
        keys=list(items[:key_count]); args=list(items[key_count:])
        checks=[]
        for i,key in enumerate(keys):
            base=i*3; limit=int(args[base]); window=int(args[base+1]); name=str(args[base+2])
            bucket=[x for x in self.events.get(key,[]) if x > self.now_ms-window]
            checks.append((key,bucket,limit,window,name))
        for key,bucket,limit,window,name in checks:
            if len(bucket) >= limit:
                return [0,1,name]
        for key,bucket,limit,window,name in checks:
            bucket.append(self.now_ms); self.events[key]=bucket
        return [1,0,""]


def test_two_replica_clients_share_one_deployment_wide_bucket():
    redis=_SharedRedis()
    a=RedisSlidingWindowRateLimiter(redis)
    b=RedisSlidingWindowRateLimiter(redis)
    checks=[("jupiter-order:ip:hashed", RULES["jupiter-order-ip"])]
    for _ in range(3):
        assert a.check(checks).allowed
        assert b.check(checks).allowed
    assert not a.check(checks).allowed
