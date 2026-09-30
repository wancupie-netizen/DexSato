import pytest

from application.dexscreener_sol_pair_resolver import (
    ExactSolPairResolverUnavailable,
    WRAPPED_SOL_MINT,
)
from application.solana_universe_workspace_service import (
    SolanaUniverseWorkspaceUnavailable,
    is_solana_universe_workspace_eligible,
    load_solana_universe_execution_feed,
    load_solana_universe_execution_record,
)


BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
PAIR = "11111111111111111111111111111111"


def _resolved_base_pair(addresses, *, min_liquidity_usd, request_get):
    assert addresses == [BONK]
    assert min_liquidity_usd == 0.0
    return {
        "rows": [
            {
                "token_address": BONK,
                "pair_address": PAIR,
                "dex_id": "raydium",
                "token_side": "base",
                "liquidity_usd": 123456.0,
                "price_usd": 0.01,
                "volume_h24_usd": 999.0,
                "price_change_h24": 2.5,
            }
        ]
    }


def test_core20_mint_builds_existing_workspace_feed_contract():
    feed = load_solana_universe_execution_feed(
        BONK,
        pair_resolver=_resolved_base_pair,
        request_get=lambda *args, **kwargs: None,
    )

    assert feed["market_feed"] == "solana_universe"
    assert len(feed["candidates"]) == 1

    candidate = feed["candidates"][0]
    assert candidate["token_address"] == BONK
    assert candidate["symbol"] == "BONK"
    assert candidate["pair_address"] == PAIR
    assert candidate["quote_address"] == WRAPPED_SOL_MINT
    assert candidate["workspace_kind"] == "solana-universe"
    assert candidate["currently_qualified"] is False


def test_non_core20_mint_never_calls_pair_resolver():
    calls = []

    def resolver(*args, **kwargs):
        calls.append(True)
        raise AssertionError("resolver must not run")

    feed = load_solana_universe_execution_feed(
        WRAPPED_SOL_MINT,
        pair_resolver=resolver,
    )

    assert feed["candidates"] == []
    assert calls == []


def test_quote_side_pair_is_rejected_to_preserve_workspace_semantics():
    def resolver(*args, **kwargs):
        return {
            "rows": [
                {
                    "token_address": BONK,
                    "pair_address": PAIR,
                    "token_side": "quote",
                    "liquidity_usd": 1000.0,
                }
            ]
        }

    assert (
        is_solana_universe_workspace_eligible(
            BONK,
            pair_resolver=resolver,
            request_get=lambda *args, **kwargs: None,
        )
        is False
    )


def test_execution_record_reuses_supplied_feed_without_resolving_again():
    feed = load_solana_universe_execution_feed(
        BONK,
        pair_resolver=_resolved_base_pair,
        request_get=lambda *args, **kwargs: None,
    )

    def fail_resolver(*args, **kwargs):
        raise AssertionError("resolver must not run when feed is supplied")

    record = load_solana_universe_execution_record(
        BONK,
        feed=feed,
        pair_resolver=fail_resolver,
    )

    assert record is feed["candidates"][0]


def test_resolver_outage_uses_explicit_unavailable_error():
    def unavailable(*args, **kwargs):
        raise ExactSolPairResolverUnavailable("offline")

    with pytest.raises(SolanaUniverseWorkspaceUnavailable):
        load_solana_universe_execution_feed(
            BONK,
            pair_resolver=unavailable,
            request_get=lambda *args, **kwargs: None,
        )