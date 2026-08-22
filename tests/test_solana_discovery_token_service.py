from application.solana_discovery_token_service import load_solana_discovery_token


TOKEN = "TokenAddressCaseSensitive123"
POOL = "PoolAddress123"
FEED = {
    "updated_label": "4 min ago",
    "candidates": [{
        "token_address": TOKEN, "pair_address": POOL, "symbol": "TEST",
        "name": "Test Token", "price_usd": 0.1, "liquidity_usd": 6000,
        "volume_24h_usd": 2000,
    }],
}


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_returns_only_exact_qualified_token_and_validates_live_pair():
    def get(url, **kwargs):
        if "dexscreener" in url:
            return Response({"pairs": [{
                "pairAddress": POOL, "baseToken": {"address": TOKEN},
                "priceUsd": "0.12", "liquidity": {"usd": 7000},
                "volume": {"h24": 3000}, "priceChange": {"h24": 4.5},
                "marketCap": 120000, "dexId": "raydium",
                "url": "https://dexscreener.com/solana/pool",
            }]})
        return Response({"data": {"attributes": {"ohlcv_list": [
            [2, .1, .13, .09, .12, 100], [1, .09, .11, .08, .1, 80]
        ]}}})

    result = load_solana_discovery_token(TOKEN, feed=FEED, request_get=get)

    assert result["quote_status"] == "LIVE"
    assert result["price_usd"] == .12
    assert result["pair_address"] == POOL
    assert len(result["chart"]) == 2


def test_rejects_unknown_or_case_changed_token():
    assert load_solana_discovery_token("unknown", feed=FEED) is None
    assert load_solana_discovery_token(TOKEN.lower(), feed=FEED) is None


def test_falls_back_to_stored_observation_when_provider_fails():
    def fail(*args, **kwargs):
        raise RuntimeError("provider failed")

    result = load_solana_discovery_token(TOKEN, feed=FEED, request_get=fail)

    assert result["quote_status"] == "STORED"
    assert result["price_usd"] == .1
    assert result["chart"] == []
