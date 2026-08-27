"""Production dependency reproducibility checks."""

from importlib.metadata import version
from pathlib import Path


EXPECTED = {
    "supabase": "2.31.0",
    "python-dotenv": "1.2.2",
    "requests": "2.34.2",
    "fastapi": "0.139.0",
    "uvicorn": "0.51.0",
}


def _requirements() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "requirements.txt"
    result = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"Production dependency must be exactly pinned: {line}"
        name, pinned = line.split("==", 1)
        result[name] = pinned
    return result


def test_production_dependencies_are_exactly_pinned():
    assert _requirements() == EXPECTED


def test_installed_direct_dependencies_match_reviewed_versions():
    assert {name: version(name) for name in EXPECTED} == EXPECTED
