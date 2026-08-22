from datetime import datetime, timezone

from application.live_market_quote_service import (
    LiveMarketQuoteUnavailable,
    clear_live_market_quote_cache,
    fetch_live_market_quote,
)


PAIR = {
    "chainId": "bsc",
    "pairAddress": "0x46cf1cf8c69595804ba91dfdd8d6b960c9b0a7c4",
    "dexId": "pancakeswap",
    "baseToken": {
        "address": "0x7130d2a12b9bcbbfaf5945b319c67e9d0870011d",
    },
    "quoteToken": {
        "address": "0x55d398326f99059ff775485246999027b3197955",
    },
    "priceUsd": "78563.40",
    "priceChange": {"h24": "4.78"},
    "volume": {"h24": "62000000"},
    "liquidity": {"usd": "13910000"},
    "marketCap": "5050000000",
}

MARKET = {
    "token": "BTC",
    "display_pair": "BTC/USDT",
    "chain_id": "bsc",
    "dex_id": "pancakeswap",
    "pair_address": PAIR["pairAddress"],
    "base_address": PAIR["baseToken"]["address"],
    "quote_address": PAIR["quoteToken"]["address"],
}


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_live_quote_uses_validated_exact_pair_and_short_cache(monkeypatch):
    clear_live_market_quote_cache()
    calls = []

    monkeypatch.setattr(
        "application.live_market_quote_service.get_market", lambda _token: MARKET
    )
    monkeypatch.setattr(
        "application.live_market_quote_service.fetch_registered_pair",
        lambda market, request_get: request_get("exact-pair", timeout=15).json()["pairs"][0],
    )

    def request_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response({"pairs": [PAIR]})

    first = fetch_live_market_quote(
        "btc",
        request_get=request_get,
        now=lambda: 100,
        recorded_at=lambda: datetime(2026, 8, 22, 5, 0, tzinfo=timezone.utc),
    )
    second = fetch_live_market_quote(
        "BTC", request_get=request_get, now=lambda: 105
    )

    assert first["status"] == "LIVE"
    assert first["price_usd"] == 78563.4
    assert first["price_change_24h"] == 4.78
    assert first["pool_address"].lower() == PAIR["pairAddress"].lower()
    assert first["policy"] == "EXACT_POOL_INFORMATIONAL_QUOTE"
    assert second["age_seconds"] == 5
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == 15


def test_provider_failure_returns_explicit_bounded_stale_quote(monkeypatch):
    clear_live_market_quote_cache()
    monkeypatch.setattr(
        "application.live_market_quote_service.get_market", lambda _token: MARKET
    )
    monkeypatch.setattr(
        "application.live_market_quote_service.fetch_registered_pair",
        lambda market, request_get: request_get("exact-pair", timeout=15).json()["pairs"][0],
    )

    fetch_live_market_quote(
        "btc",
        request_get=lambda *_a, **_k: Response({"pairs": [PAIR]}),
        now=lambda: 10,
    )

    def unavailable(*_args, **_kwargs):
        raise TimeoutError("provider timed out")

    stale = fetch_live_market_quote(
        "btc", request_get=unavailable, now=lambda: 25
    )
    assert stale["status"] == "STALE"
    assert stale["age_seconds"] == 15
    assert stale["price_usd"] == 78563.4

    try:
        fetch_live_market_quote("btc", request_get=unavailable, now=lambda: 80)
    except LiveMarketQuoteUnavailable:
        pass
    else:
        raise AssertionError("Expired stale data must fail closed.")


def test_live_quote_rejects_reference_market():
    clear_live_market_quote_cache()
    try:
        fetch_live_market_quote("xau", request_get=lambda *_a, **_k: None)
    except ValueError as error:
        assert "not available" in str(error)
    else:
        raise AssertionError("Reference markets must not expose a live quote.")
