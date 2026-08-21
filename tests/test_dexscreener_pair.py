"""Tests for exact DexScreener pair retrieval."""

import pytest
import requests

from scanner.dexscreener import fetch_registered_pair

MARKET = {"token":"ETH","chain_id":"ethereum","dex_id":"uniswap","pair_address":"0xpool","base_address":"0xweth","quote_address":"0xusdc"}


class FakeResponse:
    def __init__(self, pair, *, status_code=200):
        self.pair = pair
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")
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


def test_should_retry_one_timeout_then_succeed(caplog):
    calls = []
    delays = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        if len(calls) == 1:
            raise requests.ReadTimeout("temporary timeout")
        return FakeResponse(build_pair())

    pair = fetch_registered_pair(
        MARKET, request_get=fake_get, retry_sleep=delays.append,
    )

    assert pair["pairAddress"] == "0xpool"
    assert len(calls) == 2
    assert delays == [0.4]
    assert "external_api_retry" in caplog.text


def test_should_retry_http_429_then_succeed():
    responses = [FakeResponse(build_pair(), status_code=429), FakeResponse(build_pair())]
    delays = []

    pair = fetch_registered_pair(
        MARKET, request_get=lambda url, timeout: responses.pop(0),
        retry_sleep=delays.append,
    )

    assert pair["pairAddress"] == "0xpool"
    assert delays == [0.4]


def test_should_stop_after_two_temporary_failures(caplog):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        raise requests.ReadTimeout("provider unavailable")

    with pytest.raises(requests.ReadTimeout):
        fetch_registered_pair(
            MARKET, request_get=fake_get, retry_sleep=lambda delay: None,
        )

    assert len(calls) == 2
    assert "external_api_failed" in caplog.text


def test_should_not_retry_non_transient_http_error():
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return FakeResponse(build_pair(), status_code=404)

    with pytest.raises(requests.HTTPError):
        fetch_registered_pair(
            MARKET, request_get=fake_get, retry_sleep=lambda delay: None,
        )

    assert len(calls) == 1
