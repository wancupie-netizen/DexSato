from datetime import datetime, timezone

from application.solana_discovery_qualification import qualify_candidate


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
OBSERVED = {"token_address": "token-one", "pair_address": "pool-one", "symbol": "ONE", "name": "One", "last_seen_at": "2026-08-22T11:55:00+00:00"}
PAIR = {"chainId": "solana", "pairAddress": "pool-one", "dexId": "raydium", "baseToken": {"address": "token-one", "symbol": "ONE", "name": "One"}, "quoteToken": {"symbol": "SOL"}, "priceUsd": "0.25", "liquidity": {"usd": 12000}, "volume": {"h24": 4500}, "pairCreatedAt": 1787396400000}


def test_qualifies_identity_matched_liquid_active_pool():
    result = qualify_candidate(OBSERVED, PAIR, now=NOW)
    assert result is not None
    assert result["liquidity_usd"] == 12000
    assert result["volume_24h_usd"] == 4500
    assert "not independently verified" in result["risk_label"]


def test_rejects_unexpected_token_identity():
    pair = {**PAIR, "baseToken": {"address": "another-token"}}
    assert qualify_candidate(OBSERVED, pair, now=NOW) is None


def test_rejects_missing_or_insufficient_liquidity():
    assert qualify_candidate(OBSERVED, {**PAIR, "liquidity": {}}, now=NOW) is None
    assert qualify_candidate(OBSERVED, {**PAIR, "liquidity": {"usd": 4999}}, now=NOW) is None


def test_rejects_wrong_network_or_low_activity():
    assert qualify_candidate(OBSERVED, {**PAIR, "chainId": "bsc"}, now=NOW) is None
    assert qualify_candidate(OBSERVED, {**PAIR, "volume": {"h24": 999}}, now=NOW) is None

def test_rotating_enrichment_eventually_checks_older_resolved_pairs(monkeypatch):
    import application.solana_discovery_qualification as qualification

    qualification._ENRICHMENT_CURSOR = 0
    seen = []

    class Response:
        def __init__(self, pair_address):
            self.pair_address = pair_address

        def raise_for_status(self):
            return None

        def json(self):
            token_index = int(self.pair_address.split("-")[-1])
            token_address = f"token-{token_index}"
            return {
                "pairs": [{
                    "chainId": "solana",
                    "pairAddress": self.pair_address,
                    "baseToken": {"address": token_address, "symbol": f"T{token_index}"},
                    "quoteToken": {"symbol": "SOL"},
                    "dexId": "test",
                    "priceUsd": "1",
                    "liquidity": {"usd": 10000},
                    "volume": {"h24": 5000},
                    "pairCreatedAt": 1,
                }]
            }

    def request_get(url, timeout):
        pair_address = url.rsplit("/", 1)[-1]
        seen.append(pair_address)
        return Response(pair_address)

    candidates = {
        f"token-{index}": {
            "token_address": f"token-{index}",
            "pair_address": f"pair-{index}",
            "last_seen_at": f"2026-08-25T12:{59-index:02d}:00+00:00",
        }
        for index in range(30)
    }

    qualification._CACHE.clear()
    qualification.qualify_discovery_candidates(candidates, request_get=request_get)
    first = set(seen)
    seen.clear()

    qualification.qualify_discovery_candidates(candidates, request_get=request_get)
    second = set(seen)

    assert len(first) == qualification.MAX_CANDIDATES_CHECKED
    assert len(second) == qualification.MAX_CANDIDATES_CHECKED
    assert first != second
    assert "pair-12" in second
