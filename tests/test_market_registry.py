"""Tests for the exact-pair production registry."""

import pytest

from scanner.market_registry import get_market, load_market_registry


def test_should_load_five_registered_markets():
    registry = load_market_registry()
    assert tuple(registry) == ("BTC", "ETH", "SOL", "XRP", "SUI")
    assert registry["ETH"]["display_pair"] == "ETH/USDC"


def test_should_normalize_registered_token():
    assert get_market(" eth ")["token"] == "ETH"


def test_should_reject_unsupported_market():
    with pytest.raises(ValueError, match="Unsupported DexSato market"):
        get_market("DOGE")
