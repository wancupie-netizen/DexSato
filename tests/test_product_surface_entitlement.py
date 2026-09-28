from pathlib import Path

import pytest

from application.product_entitlement_policy import (
    PRO_ENTITLEMENTS,
    PUBLIC_ENTITLEMENTS,
)
from application.product_surface_entitlement import (
    ProductSurfaceAccessDenied,
    locked_discovery_feed,
    locked_recent_feed,
    require_product_surface,
)


@pytest.mark.parametrize(
    "capability",
    ["full_discovery", "recent_24h", "archive"],
)
def test_public_is_denied_premium_surfaces(capability: str) -> None:
    with pytest.raises(ProductSurfaceAccessDenied):
        require_product_surface(PUBLIC_ENTITLEMENTS, capability)


@pytest.mark.parametrize(
    "capability",
    ["full_discovery", "recent_24h", "archive"],
)
def test_pro_is_allowed_premium_surfaces(capability: str) -> None:
    require_product_surface(PRO_ENTITLEMENTS, capability)


def test_unknown_surface_capability_is_rejected() -> None:
    with pytest.raises(ValueError):
        require_product_surface(PRO_ENTITLEMENTS, "unknown")


def test_locked_recent_feed_leaks_no_rows_or_counts() -> None:
    feed = locked_recent_feed()

    assert feed["status"] == "locked"
    assert feed["rows"] == []
    assert feed["eligible_count"] == 0
    assert feed["access_locked"] is True
    assert feed["required_tier"] == "pro"


def test_locked_discovery_feed_leaks_no_candidates_or_archive_counts() -> None:
    feed = locked_discovery_feed("archive")

    assert feed["status"] == "locked"
    assert feed["view"] == "archive"
    assert feed["candidates"] == []
    assert feed["view_total"] == 0
    assert feed["archive_total"] == 0
    assert feed["qualified_total"] == 0
    assert feed["access_locked"] is True
    assert feed["required_tier"] == "pro"


def test_app_wires_root_without_loading_collector_archive() -> None:
    source = Path("app/main.py").read_text(encoding="utf-8")
    root = source.split("def app_home(request: Request)", 1)[1].split(
        "# TEMP-HIDE-MAJOR-ASSETS-01", 1
    )[0]

    assert "include_recent=policy.recent_24h" in root
    assert 'discovery_feed = locked_discovery_feed("rolling")' in root
    assert "load_solana_discovery_feed(" not in root
    assert "show_discovery_tab=False" in root


def test_full_discovery_routes_have_server_side_dependency_guards() -> None:
    source = Path("app/main.py").read_text(encoding="utf-8")

    guarded_paths = [
        "/discovery/solana/{token_address}",
        "/api/discovery/solana/engine",
        "/api/discovery/solana/{token_address}/candles",
        "/api/discovery/solana/{token_address}/transactions",
        "/api/discovery/solana/{token_address}/jupiter-quote",
        "/api/discovery/solana/{token_address}/wallet-balance",
        "/api/discovery/solana/{token_address}/jupiter-order",
        "/api/discovery/solana/{token_address}/jupiter-execute",
    ]
    for path in guarded_paths:
        index = source.index(path)
        window = source[max(0, index - 160): index + 240]
        assert "_require_full_discovery" in window

    assert 'require_product_surface(policy, "full_discovery")' in source
    assert 'require_product_surface(policy, "archive")' in source


def test_recent_routes_have_server_side_dependency_guards() -> None:
    source = Path("app/main.py").read_text(encoding="utf-8")

    guarded_paths = [
        "/market/recent/{token_address}",
        "/api/market/recent/{token_address}/candles",
        "/api/market/recent/{token_address}/transactions",
        "/api/market/recent/{token_address}/jupiter-quote",
        "/api/market/recent/{token_address}/wallet-balance",
        "/api/market/recent/{token_address}/jupiter-order",
        "/api/market/recent/{token_address}/jupiter-execute",
    ]
    for path in guarded_paths:
        index = source.index(path)
        window = source[max(0, index - 160): index + 240]
        assert "_require_recent_24h" in window
