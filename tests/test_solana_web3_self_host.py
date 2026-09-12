from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

JS_PATH = Path("static/js/dexsato_solana_discovery_swap.js")
VENDOR_PATH = Path("static/vendor/solana-web3/1.98.4/index.iife.min.js")
LICENSE_PATH = Path("static/vendor/solana-web3/1.98.4/LICENSE")


def _js() -> str:
    return JS_PATH.read_text(encoding="utf-8")


def _sri() -> str:
    digest = hashlib.sha384(VENDOR_PATH.read_bytes()).digest()
    return "sha384-" + base64.b64encode(digest).decode("ascii")


def test_tw_sec_007_vendored_bundle_and_license_exist():
    assert VENDOR_PATH.is_file()
    assert VENDOR_PATH.stat().st_size > 100_000
    assert LICENSE_PATH.is_file()
    assert "Permission is hereby granted" in LICENSE_PATH.read_text(encoding="utf-8")


def test_tw_sec_007_runtime_cdn_dependency_removed():
    text = _js()
    assert "cdn.jsdelivr.net" not in text
    assert "unpkg.com" not in text
    assert '/static/vendor/solana-web3/1.98.4/index.iife.min.js' in text


def test_tw_sec_007_browser_sri_matches_exact_vendored_bytes():
    text = _js()
    expected = _sri()
    assert f'script.integrity = "{expected}";' in text
    assert 'script.crossOrigin = "anonymous";' not in text


def test_tw_sec_007_lazy_load_and_fail_closed_behavior_remain():
    text = _js()
    assert "function loadSolanaWeb3()" in text
    assert "if (!web3Promise)" in text
    assert 'document.createElement("script")' in text
    assert 'reject(new Error("Solana transaction support did not initialize."));' in text
    assert 'reject(new Error("Solana transaction support could not be loaded."));' in text
    assert "web3Promise = null;" in text


def test_tw_sec_007_preserves_tw_sec_005_listener_hardening():
    text = _js()
    assert "const walletListenerRegistry = new WeakMap();" in text
    assert "function attachWalletListeners(provider)" in text
    assert "function detachWalletListeners(provider)" in text


def test_tw_sec_007_preserves_tw_sec_006_request_timeout_hardening():
    text = _js()
    assert "const controller = new AbortController();" in text
    assert 'timeoutError.code = "REQUEST_TIMEOUT";' in text
    assert "const EXECUTE_REQUEST_TIMEOUT_MS = 30000;" in text


def test_tw_sec_007_only_one_sol_web3_script_source_is_configured():
    text = _js()
    sources = re.findall(r'script\.src\s*=\s*"([^"]+)"', text)
    web3_sources = [value for value in sources if "solana-web3" in value or "@solana/web3.js" in value]
    assert web3_sources == ["/static/vendor/solana-web3/1.98.4/index.iife.min.js"]
