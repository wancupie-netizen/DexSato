from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def test_jupiter_pending_limits_and_lock_ttls_are_locked():
    swap=(ROOT/"application/jupiter_swap_service.py").read_text(encoding="utf-8")
    store=(ROOT/"application/jupiter_pending_store.py").read_text(encoding="utf-8")
    for marker in (
        "MAX_PENDING_ORDERS = 256",
        "MAX_PENDING_ORDERS_PER_WALLET = 2",
        "MAX_PENDING_ORDERS_PER_WALLET_TOKEN = 1",
        "PENDING_RESERVATION_SECONDS = 30",
    ):
        assert marker in swap
    assert "RESERVATION_TTL_SECONDS = 30" in store
    assert "EXECUTION_LOCK_TTL_MS = 45_000" in store
    assert "SET', KEYS[2], ARGV[1], 'NX', 'PX'" in store


def test_signed_transaction_and_message_digest_binding_remains_present():
    swap=(ROOT/"application/jupiter_swap_service.py").read_text(encoding="utf-8")
    assert "signed_digest = hashlib.sha256(raw).digest()" in swap
    assert "signed_message_digest = hashlib.sha256(message).digest()" in swap
    assert "hmac.compare_digest(signed_message_digest, pending.message_digest)" in swap
