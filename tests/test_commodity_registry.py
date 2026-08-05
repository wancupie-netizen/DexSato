"""Tests for the commodities market registry."""

import pytest

from scanner.commodity_registry import (
    get_commodity_market,
    load_commodity_registry,
)


def test_should_load_gold_pilot_market():
    registry = load_commodity_registry()

    assert tuple(registry) == ("XAU",)
    assert registry["XAU"]["display_pair"] == "XAU/USD"


@pytest.mark.parametrize("token", ["XAG", "WTI"])
def test_should_reject_unregistered_commodity(token):
    with pytest.raises(ValueError, match="Unsupported DexSato commodity"):
        get_commodity_market(token)
