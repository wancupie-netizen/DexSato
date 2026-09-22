from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def _read(relative): return (ROOT/relative).read_text(encoding="utf-8")


def test_frontend_contains_no_server_secret_names_or_runtime_jsdelivr():
    text=_read("presentation/dexsato_solana_discovery_token_presenter.py") + _read("static/js/dexsato_solana_discovery_swap.js")
    for secret in ("JUPITER_API_KEY","BIRDEYE_API_KEY","REDIS_URL","SUPABASE_KEY","SUPABASE_SECRET_KEY","TELEGRAM_BOT_TOKEN","OPENAI_API_KEY","DEXSATO_OPERATOR_TOKEN"):
        assert secret not in text
    assert "cdn.jsdelivr.net" not in text
    assert "/static/vendor/solana-web3/1.98.4/index.iife.min.js" in text


def test_client_timeout_and_wallet_listener_guards_remain_present():
    js=_read("static/js/dexsato_solana_discovery_swap.js")
    for marker in (
        "BALANCE_REQUEST_TIMEOUT_MS = 12000",
        "QUOTE_REQUEST_TIMEOUT_MS = 18000",
        "ORDER_REQUEST_TIMEOUT_MS = 20000",
        "EXECUTE_REQUEST_TIMEOUT_MS = 30000",
        "new AbortController()",
        "walletListenerRegistry = new WeakMap()",
        "listenerProvider",
        'window.addEventListener("pagehide"',
    ):
        assert marker in js


def test_cache_bounds_and_stale_ceilings_remain_locked():
    src=_read("application/solana_discovery_token_service.py")
    for marker in (
        "LIVE_PAIR_TTL_SECONDS = 5.0",
        "LIVE_PAIR_STALE_SECONDS = 30.0",
        "MAX_LIVE_PAIR_CACHE_ENTRIES = 500",
        "OHLCV_STALE_SECONDS = 300.0",
        "TRANSACTION_STALE_SECONDS = 120.0",
        "MAX_OHLCV_CACHE_ENTRIES = 300",
        "MAX_TRANSACTION_CACHE_ENTRIES = 300",
        "_LIVE_PAIR_INFLIGHT",
    ):
        assert marker in src


def test_production_redis_namespaces_and_fail_closed_config_are_present():
    rate=_read("application/token_workspace_rate_limit.py")
    pending=_read("application/jupiter_pending_store.py")
    readiness=_read("application/production_readiness.py")
    assert 'REDIS_PREFIX = "dexsato:ratelimit"' in rate
    assert 'DEFAULT_PREFIX = "dexsato:jupiter"' in pending
    assert "Production requires DEXSATO_RATE_LIMIT_STORE=redis." in rate
    assert "DEXSATO_PENDING_STORE=redis is required in production." in readiness
    assert "DEXSATO_RATE_LIMIT_STORE=redis is required in production." in readiness
