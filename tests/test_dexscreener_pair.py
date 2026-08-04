"""Tests for exact DexScreener pair retrieval."""

import pytest

from scanner.dexscreener import fetch_registered_pair

MARKET = {"token":"ETH","chain_id":"ethereum","dex_id":"uniswap","pair_address":"0xpool","base_address":"0xweth","quote_address":"0xusdc"}


class FakeResponse:
    def __init__(self, pair):
        self.pair = pair

    def raise_for_status(self):
        return None

    def json(self):
        return {"pairs": [self.pair]}


def build_pair(*, base_address="0xweth"):
    return {"chainId":"ethereum","dexId":"uniswap","pairAddress":"0xpool","baseToken":{"address":base_address,"symbol":"WETH"},"quoteToken":{"address":"0xusdc","symbol":"USDC"}}


def test_should_return_exact_registered_pair():
    requested = {}

    def fake_get(url, timeout):
        requested.update(url=url, timeout=timeout)
        return FakeResponse(build_pair())

    pair = fetch_registered_pair(MARKET, request_get=fake_get)
    assert pair["pairAddress"] == "0xpool"
    assert requested["timeout"] == 15
    assert requested["url"].endswith("/ethereum/0xpool")


def test_should_reject_contract_mismatch():
    def fake_get(url, timeout):
        return FakeResponse(build_pair(base_address="0xfake"))

    with pytest.raises(RuntimeError, match="baseToken.address"):
        fetch_registered_pair(MARKET, request_get=fake_get)
