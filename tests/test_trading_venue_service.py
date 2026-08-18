from application.trading_venue_service import (
    fetch_trading_venues,
    rank_trading_venues,
)


MARKET = {
    "display_pair": "SOL/USDT",
    "chain_id": "solana",
    "base_address": "So11111111111111111111111111111111111111112",
}


def _pair(dex_id, volume, liquidity, *, quote="USDT", address=None):
    return {
        "chainId": "solana",
        "dexId": dex_id,
        "baseToken": {
            "address": address or MARKET["base_address"],
            "symbol": "SOL",
        },
        "quoteToken": {"symbol": quote},
        "volume": {"h24": volume},
        "liquidity": {"usd": liquidity},
        "url": f"https://dexscreener.com/solana/{dex_id}",
    }


def test_should_rank_verified_venues_by_volume_and_dedupe_dex():
    venues = rank_trading_venues(
        market=MARKET,
        pairs=[
            _pair("raydium", 100, 500),
            _pair("orca", 300, 400),
            _pair("raydium", 200, 600),
            _pair("cetus", 900, 900, quote="USDC"),
            _pair("fake", 1000, 1000, address="other-token"),
        ],
    )

    assert [venue["name"] for venue in venues] == ["Orca", "Raydium"]
    assert venues[1]["volume_24h"] == 200
    assert all(venue["type"] == "DEX" for venue in venues)


def test_should_fetch_registered_token_pairs():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return []

    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return Response()

    assert fetch_trading_venues("SOL", request_get=fake_get) == []
    assert "/token-pairs/v1/solana/" in calls[0][0]
    assert calls[0][1] == 15
