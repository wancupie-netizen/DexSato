from unittest.mock import patch

from application.discovery_storage import (
    LEGACY_DISCOVERY_STORAGE,
    discovery_storage_dir,
    validate_production_runtime,
)


def _assert_runtime_error(environment, expected):
    with patch.dict("os.environ", environment, clear=True):
        try:
            validate_production_runtime()
        except RuntimeError as error:
            assert expected in str(error)
        else:
            raise AssertionError("Expected unsafe production runtime to fail")


def test_development_preserves_the_existing_project_storage_path():
    with patch.dict("os.environ", {}, clear=True):
        resolved = discovery_storage_dir()
    assert resolved.name == LEGACY_DISCOVERY_STORAGE.name
    assert resolved.is_absolute()


def test_production_requires_an_absolute_configured_storage_path():
    _assert_runtime_error({"DEXSATO_ENV": "production"}, "required")
    _assert_runtime_error(
        {
            "DEXSATO_ENV": "production",
            "DEXSATO_DISCOVERY_STORAGE_DIR": "relative/storage",
        },
        "absolute",
    )


def test_production_requires_an_existing_persistent_directory(tmp_path):
    missing = tmp_path / "missing"
    _assert_runtime_error(
        {
            "DEXSATO_ENV": "production",
            "DEXSATO_DISCOVERY_STORAGE_DIR": str(missing),
            "DEXSATO_WEB_WORKERS": "1",
        },
        "existing persistent volume",
    )


def test_production_storage_write_probe_is_removed(tmp_path):
    environment = {
        "DEXSATO_ENV": "production",
        "DEXSATO_DISCOVERY_STORAGE_DIR": str(tmp_path),
        "DEXSATO_WEB_WORKERS": "1",
    }
    with patch.dict("os.environ", environment, clear=True):
        assert validate_production_runtime() == tmp_path
    assert list(tmp_path.iterdir()) == []


def test_production_rejects_multi_worker_runtime(tmp_path):
    for variable in ("DEXSATO_WEB_WORKERS", "WEB_CONCURRENCY", "UVICORN_WORKERS"):
        _assert_runtime_error(
            {
                "DEXSATO_ENV": "production",
                "DEXSATO_DISCOVERY_STORAGE_DIR": str(tmp_path),
                variable: "2",
            },
            "exactly one web worker",
        )


def test_configured_storage_survives_a_fresh_resolution(tmp_path):
    marker = tmp_path / "archive-marker"
    marker.write_text("persistent", encoding="utf-8")
    environment = {"DEXSATO_DISCOVERY_STORAGE_DIR": str(tmp_path)}
    with patch.dict("os.environ", environment, clear=True):
        first = discovery_storage_dir()
        second = discovery_storage_dir()
    assert first == second == tmp_path
    assert (second / marker.name).read_text(encoding="utf-8") == "persistent"
