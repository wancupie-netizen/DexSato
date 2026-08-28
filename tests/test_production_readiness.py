import json
import sqlite3
from unittest.mock import patch

from application.production_readiness import (
    collector_storage_ready,
    discovery_archive_ready,
    production_configuration_ready,
    validate_production_configuration,
)


def _production_environment(**overrides):
    environment = {
        "DEXSATO_ENV": "production",
        "JUPITER_API_KEY": "jupiter-server-key",
        "BIRDEYE_API_KEY": "birdeye-server-key",
        "SOLANA_RPC_URL": "https://api.mainnet-beta.solana.com",
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
    with patch.dict("os.environ", {}, clear=True):
        assert validate_production_configuration() is None
        assert production_configuration_ready() is True


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
