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
