"""Shared Jupiter pending-order coordination for multi-replica deployments."""

from __future__ import annotations

import hashlib
import json
import math
import secrets
from dataclasses import dataclass
from typing import Any


RESERVATION_TTL_SECONDS = 30
EXECUTION_LOCK_TTL_MS = 45_000
DEFAULT_PREFIX = "dexsato:jupiter"


class JupiterPendingStoreUnavailable(RuntimeError):
    """Raised when shared pending state cannot be reached safely."""


class JupiterPendingStoreLimit(RuntimeError):
    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


class JupiterPendingStoreConflict(RuntimeError):
    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


_RESERVE_LUA = r"""
local now = tonumber(ARGV[1])
local expiry = tonumber(ARGV[2])
local member = ARGV[3]
local payload = ARGV[4]
local ttl = tonumber(ARGV[5])
local global_limit = tonumber(ARGV[6])
local wallet_limit = tonumber(ARGV[7])
local wallet_token_limit = tonumber(ARGV[8])

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now)

if redis.call('ZCARD', KEYS[1]) >= global_limit then return 'GLOBAL_LIMIT' end
if redis.call('ZCARD', KEYS[2]) >= wallet_limit then return 'WALLET_LIMIT' end
if redis.call('ZCARD', KEYS[3]) >= wallet_token_limit then return 'WALLET_TOKEN_LIMIT' end

redis.call('ZADD', KEYS[1], expiry, member)
redis.call('ZADD', KEYS[2], expiry, member)
redis.call('ZADD', KEYS[3], expiry, member)
redis.call('SET', KEYS[4], payload, 'EX', ttl)
return 'OK'
"""

_COMMIT_LUA = r"""
local now = tonumber(ARGV[1])
local expiry = tonumber(ARGV[2])
local reservation_member = ARGV[3]
local order_member = ARGV[4]
local pending_payload = ARGV[5]
local expected_wallet = ARGV[6]
local expected_token = ARGV[7]
local max_pending = tonumber(ARGV[8])
local ttl = tonumber(ARGV[9])

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[4], '-inf', now)

local reservation_raw = redis.call('GET', KEYS[5])
if not reservation_raw then return 'RESERVATION_MISSING' end
local reservation = cjson.decode(reservation_raw)
if reservation['wallet_address'] ~= expected_wallet or reservation['token_address'] ~= expected_token then
  return 'RESERVATION_MISMATCH'
end
if redis.call('EXISTS', KEYS[6]) == 1 then return 'DUPLICATE_REQUEST' end
if redis.call('ZCARD', KEYS[4]) >= max_pending then return 'HARD_LIMIT' end

redis.call('ZREM', KEYS[1], reservation_member)
redis.call('ZREM', KEYS[2], reservation_member)
redis.call('ZREM', KEYS[3], reservation_member)
redis.call('ZADD', KEYS[1], expiry, order_member)
redis.call('ZADD', KEYS[2], expiry, order_member)
redis.call('ZADD', KEYS[3], expiry, order_member)
redis.call('ZADD', KEYS[4], expiry, order_member)
redis.call('DEL', KEYS[5])
redis.call('SET', KEYS[6], pending_payload, 'EX', ttl)
return 'OK'
"""

_RELEASE_RESERVATION_LUA = r"""
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
redis.call('ZREM', KEYS[3], ARGV[1])
redis.call('DEL', KEYS[4])
return 1
"""

_BEGIN_EXECUTION_LUA = r"""
local raw = redis.call('GET', KEYS[1])
if not raw then return 'MISSING' end
local locked = redis.call('SET', KEYS[2], ARGV[1], 'NX', 'PX', ARGV[3])
if not locked then return 'EXECUTING' end

local payload = cjson.decode(raw)
local existing = payload['signed_digest']
if existing and existing ~= cjson.null and existing ~= '' and existing ~= ARGV[2] then
  if redis.call('GET', KEYS[2]) == ARGV[1] then redis.call('DEL', KEYS[2]) end
  return 'DIGEST_MISMATCH'
end

payload['signed_digest'] = ARGV[2]
local ttl = redis.call('PTTL', KEYS[1])
if ttl <= 0 then
  if redis.call('GET', KEYS[2]) == ARGV[1] then redis.call('DEL', KEYS[2]) end
  return 'MISSING'
end
redis.call('SET', KEYS[1], cjson.encode(payload), 'PX', ttl)
return 'OK'
"""

_RELEASE_LOCK_LUA = r"""
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

_COMPLETE_LUA = r"""
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
redis.call('ZREM', KEYS[3], ARGV[1])
redis.call('ZREM', KEYS[4], ARGV[1])
redis.call('DEL', KEYS[5])
if redis.call('GET', KEYS[6]) == ARGV[2] then redis.call('DEL', KEYS[6]) end
return 1
"""


@dataclass(slots=True)
class RedisJupiterPendingStore:
    client: Any
    prefix: str = DEFAULT_PREFIX

    @classmethod
    def from_url(cls, url: str, *, prefix: str = DEFAULT_PREFIX) -> "RedisJupiterPendingStore":
        try:
            import redis
            client = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
                health_check_interval=30,
            )
        except Exception as error:
            raise JupiterPendingStoreUnavailable("Redis pending store could not be configured.") from error
        return cls(client=client, prefix=prefix)

    def ping(self) -> None:
        try:
            if self.client.ping() is not True:
                raise JupiterPendingStoreUnavailable("Redis pending store health check failed.")
        except JupiterPendingStoreUnavailable:
            raise
        except Exception as error:
            raise JupiterPendingStoreUnavailable("Redis pending store is unavailable.") from error

    @staticmethod
    def _identity(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _global(self) -> str:
        return f"{self.prefix}:active"

    def _pending_index(self) -> str:
        return f"{self.prefix}:pending_index"

    def _wallet(self, wallet: str) -> str:
        return f"{self.prefix}:wallet:{self._identity(wallet)}"

    def _wallet_token(self, wallet: str, token: str) -> str:
        return f"{self.prefix}:wallet_token:{self._identity(wallet + '|' + token)}"

    def _reservation(self, reservation_id: str) -> str:
        return f"{self.prefix}:reservation:{reservation_id}"

    def _pending(self, request_id: str) -> str:
        return f"{self.prefix}:pending:{request_id}"

    def _execution(self, request_id: str) -> str:
        return f"{self.prefix}:execute:{request_id}"

    @staticmethod
    def _json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def _eval(self, script: str, keys: list[str], args: list[Any]) -> Any:
        try:
            return self.client.eval(script, len(keys), *keys, *args)
        except Exception as error:
            raise JupiterPendingStoreUnavailable("Redis pending store operation failed.") from error

    def reserve(
        self,
        reservation_id: str,
        token_address: str,
        wallet_address: str,
        now_epoch: float,
        *,
        admission_limit: int,
        wallet_limit: int,
        wallet_token_limit: int,
    ) -> None:
        expiry = now_epoch + RESERVATION_TTL_SECONDS
        member = "r:" + reservation_id
        payload = self._json({
            "token_address": token_address,
            "wallet_address": wallet_address,
            "expires_at": expiry,
        })
        result = self._eval(
            _RESERVE_LUA,
            [self._global(), self._wallet(wallet_address), self._wallet_token(wallet_address, token_address),
             self._reservation(reservation_id)],
            [now_epoch, expiry, member, payload, RESERVATION_TTL_SECONDS,
             admission_limit, wallet_limit, wallet_token_limit],
        )
        if result == "GLOBAL_LIMIT":
            raise JupiterPendingStoreLimit("global")
        if result == "WALLET_LIMIT":
            raise JupiterPendingStoreLimit("wallet")
        if result == "WALLET_TOKEN_LIMIT":
            raise JupiterPendingStoreLimit("wallet_token")
        if result != "OK":
            raise JupiterPendingStoreUnavailable("Redis pending reservation returned an invalid result.")

    def release_reservation(self, reservation_id: str) -> None:
        try:
            raw = self.client.get(self._reservation(reservation_id))
        except Exception as error:
            raise JupiterPendingStoreUnavailable("Redis pending store operation failed.") from error
        if not raw:
            return
        try:
            payload = json.loads(raw)
            wallet = str(payload["wallet_address"])
            token = str(payload["token_address"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise JupiterPendingStoreUnavailable("Redis pending reservation was invalid.") from error
        self._eval(
            _RELEASE_RESERVATION_LUA,
            [self._global(), self._wallet(wallet), self._wallet_token(wallet, token),
             self._reservation(reservation_id)],
            ["r:" + reservation_id],
        )

    def commit(
        self,
        reservation_id: str,
        request_id: str,
        pending_payload: dict[str, Any],
        now_epoch: float,
        expires_epoch: float,
        *,
        max_pending: int,
    ) -> None:
        wallet = str(pending_payload["wallet_address"])
        token = str(pending_payload["token_address"])
        ttl = max(1, int(math.ceil(expires_epoch - now_epoch)))
        result = self._eval(
            _COMMIT_LUA,
            [self._global(), self._wallet(wallet), self._wallet_token(wallet, token), self._pending_index(),
             self._reservation(reservation_id), self._pending(request_id)],
            [now_epoch, expires_epoch, "r:" + reservation_id, "o:" + request_id,
             self._json(pending_payload), wallet, token, max_pending, ttl],
        )
        if result == "RESERVATION_MISSING":
            raise JupiterPendingStoreConflict("reservation_missing")
        if result == "RESERVATION_MISMATCH":
            raise JupiterPendingStoreConflict("reservation_mismatch")
        if result == "DUPLICATE_REQUEST":
            raise JupiterPendingStoreConflict("duplicate_request")
        if result == "HARD_LIMIT":
            raise JupiterPendingStoreLimit("hard")
        if result != "OK":
            raise JupiterPendingStoreUnavailable("Redis pending commit returned an invalid result.")

    def get_pending(self, request_id: str) -> dict[str, Any] | None:
        try:
            raw = self.client.get(self._pending(request_id))
        except Exception as error:
            raise JupiterPendingStoreUnavailable("Redis pending store operation failed.") from error
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as error:
            raise JupiterPendingStoreUnavailable("Redis pending order was invalid.") from error
        if not isinstance(payload, dict):
            raise JupiterPendingStoreUnavailable("Redis pending order was invalid.")
        return payload

    def begin_execution(self, request_id: str, signed_digest: str) -> str:
        owner = secrets.token_hex(24)
        result = self._eval(
            _BEGIN_EXECUTION_LUA,
            [self._pending(request_id), self._execution(request_id)],
            [owner, signed_digest, EXECUTION_LOCK_TTL_MS],
        )
        if result == "MISSING":
            raise JupiterPendingStoreConflict("missing")
        if result == "EXECUTING":
            raise JupiterPendingStoreConflict("executing")
        if result == "DIGEST_MISMATCH":
            raise JupiterPendingStoreConflict("digest_mismatch")
        if result != "OK":
            raise JupiterPendingStoreUnavailable("Redis execution lock returned an invalid result.")
        return owner

    def release_execution(self, request_id: str, owner: str) -> None:
        self._eval(_RELEASE_LOCK_LUA, [self._execution(request_id)], [owner])

    def complete(self, request_id: str, owner: str, wallet: str, token: str) -> None:
        self._eval(
            _COMPLETE_LUA,
            [self._global(), self._wallet(wallet), self._wallet_token(wallet, token), self._pending_index(),
             self._pending(request_id), self._execution(request_id)],
            ["o:" + request_id, owner],
        )
