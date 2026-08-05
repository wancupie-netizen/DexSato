"""Tests for the Twelve Data commodities adapter."""

import pytest

from scanner.twelve_data import (
    fetch_commodity_quote,
    normalize_commodity_quote,
)

MARKET = {
    "token": "XAU",
    "name": "Gold",
    "display_pair": "XAU/USD",
    "provider_symbol": "XAU/USD",
    "market_id": "twelvedata:XAU/USD",
}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_should_fetch_registered_commodity_quote():
    requested = {}

    def fake_get(url, params, timeout):
        requested.update(url=url, params=params, timeout=timeout)
        return FakeResponse({"symbol": "XAU/USD", "close": "4050.25"})

    quote = fetch_commodity_quote(
        MARKET,
        api_key="test-key",
        request_get=fake_get,
    )

    assert quote["close"] == "4050.25"
    assert requested["params"]["symbol"] == "XAU/USD"
    assert requested["timeout"] == 15


def test_should_reject_provider_error():
    def fake_get(url, params, timeout):
        return FakeResponse(
            {"status": "error", "code": 401, "message": "Invalid key"}
        )

    with pytest.raises(RuntimeError, match="Invalid key"):
        fetch_commodity_quote(
            MARKET,
            api_key="bad-key",
            request_get=fake_get,
        )


def test_should_normalize_without_fake_liquidity():
    event = normalize_commodity_quote(
        MARKET,
        {"symbol": "XAU/USD", "close": "4050.25"},
    )

    assert event["token"] == "XAU"
    assert event["pair"] == "XAU/USD"
    assert event["price"] == "4050.25"
    assert event["liquidity"] is None
    assert event["volume_24h"] is None
    assert event["pair_address"] == "twelvedata:XAU/USD"
    assert event["source"] == "Twelve Data"
