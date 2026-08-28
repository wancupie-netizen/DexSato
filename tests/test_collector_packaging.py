import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = (
    "application/discovery_storage.py",
    "research/__init__.py",
    "research/phase0_solana_discovery_probe_v2.py",
    "research/phase0_seven_day_collector.py",
)


def test_collector_runtime_manifest_is_complete():
    missing = [relative for relative in RUNTIME_FILES if not (PROJECT_ROOT / relative).is_file()]
    assert missing == []


def test_probe_import_performs_no_network_or_file_output():
    before = set(PROJECT_ROOT.iterdir())
    with patch("urllib.request.urlopen") as request:
        __import__("research.phase0_solana_discovery_probe_v2")
    assert request.call_count == 0
    assert set(PROJECT_ROOT.iterdir()) == before


def test_collector_imports_from_an_isolated_clean_runtime_tree(tmp_path):
    for relative in RUNTIME_FILES:
        source = PROJECT_ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (tmp_path / "application" / "__init__.py").write_text("", encoding="utf-8")

    code = (
        "import sys; "
        f"sys.path.insert(0, {str(tmp_path)!r}); "
        "import research.phase0_seven_day_collector as collector; "
        "assert callable(collector.collect_birdeye); "
        "assert callable(collector.collect_dex_profiles); "
        "assert callable(collector.enrich)"
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"BIRDEYE_API_KEY", "DEXSATO_DISCOVERY_STORAGE_DIR"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.rglob("state.json")) == []
    assert list(tmp_path.rglob("status.json")) == []
