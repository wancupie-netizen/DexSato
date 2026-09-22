import json
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from application.production_readiness import (
    collector_fresh,
    collector_storage_ready,
    discovery_archive_ready,
    production_configuration_ready,
    validate_production_configuration,
)


@pytest.fixture(autouse=True)
def _clear_state_validation_cache():
    from application import production_readiness

    production_readiness._state_validation_cache.clear()
    yield
    production_readiness._state_validation_cache.clear()


def _production_environment(**overrides):
    environment = {
        "DEXSATO_ENV": "production",
        "JUPITER_API_KEY": "jupiter-server-key",
        "BIRDEYE_API_KEY": "birdeye-server-key",
        "SOLANA_RPC_URL": "https://api.mainnet-beta.solana.com",
        "DEXSATO_PENDING_STORE": "redis",
        "DEXSATO_RATE_LIMIT_STORE": "redis",
        "REDIS_URL": "redis://redis.internal:6379/0",
    }
    environment.update(overrides)
    return environment


def _expect_configuration_error(environment, expected):
    with patch.dict("os.environ", environment, clear=True):
        try:
            validate_production_configuration()
        except RuntimeError as error:
            assert expected in str(error)
        else:
            raise AssertionError("Expected unsafe production configuration to fail")


def test_development_does_not_require_production_provider_keys():
    from application.jupiter_fee_policy import get_fee_policy

    get_fee_policy.cache_clear()
    try:
        with patch.dict("os.environ", {}, clear=True):
            assert validate_production_configuration() is None
            assert production_configuration_ready() is True
    finally:
        get_fee_policy.cache_clear()


def test_fee_configuration_rejects_invalid_enabled_policy():
    from application.jupiter_fee_policy import get_fee_policy
    get_fee_policy.cache_clear()
    try:
        with patch.dict("os.environ", _production_environment(
            DEXSATO_JUPITER_FEE_ENABLED="true",
            DEXSATO_JUPITER_REFERRAL_ACCOUNT="invalid",
            DEXSATO_JUPITER_REFERRAL_FEE_BPS="50",
        ), clear=True):
            assert production_configuration_ready() is False
    finally:
        get_fee_policy.cache_clear()


def test_fee_configuration_drift_requires_restart():
    from application.jupiter_fee_policy import get_fee_policy
    get_fee_policy.cache_clear()
    try:
        with patch.dict("os.environ", _production_environment(
            DEXSATO_JUPITER_FEE_ENABLED="true",
            DEXSATO_JUPITER_REFERRAL_ACCOUNT="5q9Rk7oLhpxyoUstjKqbJxV3xnAi7Zucqsuw6NCzzNQQ",
            DEXSATO_JUPITER_REFERRAL_FEE_BPS="50",
        ), clear=True):
            assert production_configuration_ready() is True
            with patch.dict("os.environ", {"DEXSATO_JUPITER_REFERRAL_FEE_BPS": "60"}):
                assert production_configuration_ready() is False
    finally:
        get_fee_policy.cache_clear()


def test_production_requires_core_server_side_provider_keys():
    _expect_configuration_error(
        _production_environment(JUPITER_API_KEY=""),
        "JUPITER_API_KEY",
    )
    _expect_configuration_error(
        _production_environment(BIRDEYE_API_KEY="your-birdeye-key"),
        "BIRDEYE_API_KEY",
    )


def test_production_requires_https_rpc_without_embedded_credentials():
    _expect_configuration_error(
        _production_environment(SOLANA_RPC_URL="http://rpc.example"),
        "SOLANA_RPC_URL",
    )
    _expect_configuration_error(
        _production_environment(SOLANA_RPC_URL="https://user:secret@rpc.example"),
        "SOLANA_RPC_URL",
    )


def test_internal_endpoints_require_a_strong_operator_token():
    _expect_configuration_error(
        _production_environment(
            DEXSATO_INTERNAL_ENDPOINTS_ENABLED="true",
            DEXSATO_OPERATOR_TOKEN="short",
        ),
        "at least 32",
    )


def test_valid_production_configuration_returns_no_secret_material():
    with patch.dict("os.environ", _production_environment(), clear=True):
        assert validate_production_configuration() is None
        assert production_configuration_ready() is True


def test_product_identity_configuration_is_inert_until_enabled():
    with patch.dict("os.environ", _production_environment(), clear=True):
        assert validate_production_configuration() is None


def test_enabled_product_identity_requires_separate_current_supabase_keys():
    base = _production_environment(
        DEXSATO_PRODUCT_AUTH_ENABLED="true",
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
        SUPABASE_SECRET_KEY="sb_secret_test",
    )
    with patch.dict("os.environ", base, clear=True):
        assert validate_production_configuration() is None
    _expect_configuration_error(
        {**base, "SUPABASE_PUBLISHABLE_KEY": ""},
        "SUPABASE_PUBLISHABLE_KEY",
    )
    _expect_configuration_error(
        {**base, "SUPABASE_SECRET_KEY": "legacy-service-role-key"},
        "SUPABASE_SECRET_KEY",
    )
    _expect_configuration_error(
        {**base, "SUPABASE_URL": "http://project.supabase.co"},
        "SUPABASE_URL",
    )


def test_collector_integrity_requires_expected_json_mappings(tmp_path):
    (tmp_path / "state.json").write_text(
        json.dumps({"candidates": {}}), encoding="utf-8"
    )
    (tmp_path / "status.json").write_text(
        json.dumps({"metrics": {}}), encoding="utf-8"
    )
    assert collector_storage_ready(tmp_path) is True
    (tmp_path / "state.json").write_text('{"candidates": []}', encoding="utf-8")
    assert collector_storage_ready(tmp_path) is False


def test_state_cache_skips_second_json_parse_for_identical_bytes(tmp_path, monkeypatch):
    from application import production_readiness

    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"candidates": {"A": {}}}), encoding="utf-8")
    (tmp_path / "status.json").write_text(json.dumps({"metrics": {}}), encoding="utf-8")

    original_loads = production_readiness.json.loads
    state_parse_count = 0

    def counted_loads(value, *args, **kwargs):
        nonlocal state_parse_count
        if isinstance(value, bytes):
            state_parse_count += 1
        return original_loads(value, *args, **kwargs)

    monkeypatch.setattr(production_readiness.json, "loads", counted_loads)
    assert collector_storage_ready(tmp_path) is True
    assert collector_storage_ready(tmp_path) is True
    assert state_parse_count == 1


def test_state_cache_detects_same_path_in_place_overwrite(tmp_path):
    state = tmp_path / "state.json"
    status = tmp_path / "status.json"
    state.write_text('{"candidates": {}}', encoding="utf-8")
    status.write_text('{"metrics": {}}', encoding="utf-8")
    assert collector_storage_ready(tmp_path) is True
    state.write_text('{"candidates": []}', encoding="utf-8")
    assert collector_storage_ready(tmp_path) is False


def test_state_cache_invalidates_atomic_valid_to_invalid(tmp_path):
    state = tmp_path / "state.json"
    status = tmp_path / "status.json"
    state.write_text('{"candidates": {}}', encoding="utf-8")
    status.write_text('{"metrics": {}}', encoding="utf-8")
    assert collector_storage_ready(tmp_path) is True
    replacement = tmp_path / "state.json.tmp"
    replacement.write_text('{"candidates": []}', encoding="utf-8")
    replacement.replace(state)
    assert collector_storage_ready(tmp_path) is False


def test_state_cache_recovers_atomic_invalid_to_valid(tmp_path):
    state = tmp_path / "state.json"
    status = tmp_path / "status.json"
    state.write_text('{"candidates": []}', encoding="utf-8")
    status.write_text('{"metrics": {}}', encoding="utf-8")
    assert collector_storage_ready(tmp_path) is False
    replacement = tmp_path / "state.json.tmp"
    replacement.write_text('{"candidates": {}}', encoding="utf-8")
    replacement.replace(state)
    assert collector_storage_ready(tmp_path) is True


def test_state_cache_never_returns_stale_true_after_delete(tmp_path):
    state = tmp_path / "state.json"
    status = tmp_path / "status.json"
    state.write_text('{"candidates": {}}', encoding="utf-8")
    status.write_text('{"metrics": {}}', encoding="utf-8")
    assert collector_storage_ready(tmp_path) is True
    state.unlink()
    assert collector_storage_ready(tmp_path) is False


def test_status_json_is_still_validated_every_call(tmp_path):
    state = tmp_path / "state.json"
    status = tmp_path / "status.json"
    state.write_text('{"candidates": {}}', encoding="utf-8")
    status.write_text('{"metrics": {}}', encoding="utf-8")
    assert collector_storage_ready(tmp_path) is True
    status.write_text('{"metrics": []}', encoding="utf-8")
    assert collector_storage_ready(tmp_path) is False


def test_state_cache_retries_generation_changed_during_read(tmp_path, monkeypatch):
    from application import production_readiness

    state = tmp_path / "state.json"
    status = tmp_path / "status.json"
    state.write_text('{"candidates": {}}', encoding="utf-8")
    status.write_text('{"metrics": {}}', encoding="utf-8")

    original = production_readiness._state_fingerprint
    calls = 0

    def unstable_once(path):
        nonlocal calls
        calls += 1
        value = original(path)
        if calls == 2:
            return (value[0], value[1], value[2] + 1, value[3], value[4])
        return value

    monkeypatch.setattr(production_readiness, "_state_fingerprint", unstable_once)
    assert collector_storage_ready(tmp_path) is True
    assert calls >= 4


def test_collector_freshness_accepts_recent_generated_at(tmp_path):
    now = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    (tmp_path / "status.json").write_text(
        json.dumps({"generated_at": (now - timedelta(minutes=15)).isoformat()}),
        encoding="utf-8",
    )
    assert collector_fresh(tmp_path, stale_minutes=45, now=now) is True


def test_collector_freshness_rejects_stale_or_invalid_status(tmp_path):
    now = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    (tmp_path / "status.json").write_text(
        json.dumps({"generated_at": (now - timedelta(minutes=46)).isoformat()}),
        encoding="utf-8",
    )
    assert collector_fresh(tmp_path, stale_minutes=45, now=now) is False
    (tmp_path / "status.json").write_text(
        json.dumps({"generated_at": "not-a-time"}), encoding="utf-8"
    )
    assert collector_fresh(tmp_path, stale_minutes=45, now=now) is False


def test_archive_integrity_is_read_only_and_requires_discoveries_table(tmp_path):
    archive_name = "archive.sqlite3"
    archive = tmp_path / archive_name
    with sqlite3.connect(archive) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER)")
    assert discovery_archive_ready(tmp_path, archive_name) is False

    with sqlite3.connect(archive) as connection:
        connection.execute("CREATE TABLE discoveries (token_address TEXT PRIMARY KEY)")
    before = archive.stat().st_size
    assert discovery_archive_ready(tmp_path, archive_name) is True
    assert archive.stat().st_size == before

    archive.write_bytes(b"corrupt")
    assert discovery_archive_ready(tmp_path, archive_name) is False
