from unittest.mock import Mock

import pytest

from application.jupiter_quote_service import (
    JUPITER_ORDER_URL,
    WRAPPED_SOL_MINT,
    JupiterQuoteNotConfigured,
    JupiterQuoteUnavailable,
    fetch_jupiter_quote,
)


TOKEN = "11111111111111111111111111111111"
FEED = {"candidates": [{"token_address": TOKEN, "symbol": "TEST"}]}


def _response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def test_returns_quote_without_taker_or_transaction_material():
    request_get = Mock(return_value=_response({
        "inputMint": WRAPPED_SOL_MINT,
        "outputMint": TOKEN,
        "inAmount": "100000000",
        "outAmount": "2500000",
        "outputDecimals": 6,
        "router": "JupiterZ",
        "mode": "ExactIn",
        "priceImpactPct": "0.12",
        "feeBps": 5,
        "platformFee": {"amount": "100", "feeBps": 5, "feeMint": TOKEN},
        "transaction": None,
    }))

    quote = fetch_jupiter_quote(
        TOKEN, "0.1", api_key="server-secret", feed=FEED, request_get=request_get,
    )

    assert quote["status"] == "QUOTE_READY"
    assert quote["output_amount_ui"] == "2.5"
    assert quote["output_decimals"] == 6
    assert quote["output_decimals_source"] == "Jupiter"
    assert quote["quote_only"] is True
    assert quote["execution_enabled"] is False
    assert quote["transaction_available"] is False
    assert quote["dexsato_integrator_fee_bps"] == 0
    assert "transaction" not in quote and "requestId" not in quote

    call = request_get.call_args
    assert call.args[0] == JUPITER_ORDER_URL
    assert call.kwargs["params"] == {
        "inputMint": WRAPPED_SOL_MINT,
        "outputMint": TOKEN,
        "amount": "100000000",
    }
    assert "taker" not in call.kwargs["params"]
    assert call.kwargs["headers"]["x-api-key"] == "server-secret"


def test_resolves_missing_output_decimals_from_solana_mint():
    request_get = Mock(return_value=_response({
        "outputMint": TOKEN,
        "outAmount": "162243708607",
        "otherAmountThreshold": "160621271520",
        "transaction": None,
    }))
    request_post = Mock(return_value=_response({
        "jsonrpc": "2.0",
        "result": {"value": {"amount": "1", "decimals": 9}},
    }))

    quote = fetch_jupiter_quote(
        TOKEN, "0.1", api_key="key", feed=FEED,
        request_get=request_get, request_post=request_post,
    )

    assert quote["output_amount_ui"] == "162.243708607"
    assert quote["minimum_received_ui"] == "160.62127152"
    assert quote["output_decimals"] == 9
    assert quote["output_decimals_source"] == "Solana mint"
    assert request_post.call_args.kwargs["json"]["method"] == "getTokenSupply"


def test_keeps_explicit_raw_fallback_when_mint_decimals_are_unavailable():
    request_get = Mock(return_value=_response({
        "outputMint": TOKEN, "outAmount": "123", "transaction": None,
    }))
    request_post = Mock(side_effect=RuntimeError("rpc unavailable"))

    quote = fetch_jupiter_quote(
        TOKEN, "0.1", api_key="key", feed=FEED,
        request_get=request_get, request_post=request_post,
    )

    assert quote["output_amount_ui"] is None
    assert quote["output_decimals"] is None
    assert quote["output_decimals_source"] is None


def test_rejects_unknown_candidate_and_invalid_amount():
    with pytest.raises(ValueError, match="qualified"):
        fetch_jupiter_quote(TOKEN, "0.1", api_key="key", feed={"candidates": []})
    with pytest.raises(ValueError, match="between"):
        fetch_jupiter_quote(TOKEN, "1000", api_key="key", feed=FEED)


def test_requires_server_api_key():
    with pytest.raises(JupiterQuoteNotConfigured):
        fetch_jupiter_quote(TOKEN, "0.1", api_key="", feed=FEED)


def test_fails_closed_if_jupiter_returns_transaction_or_wrong_mint():
    transaction_response = Mock(return_value=_response({
        "outputMint": TOKEN, "outAmount": "1", "transaction": "unsigned-data",
    }))
    with pytest.raises(JupiterQuoteUnavailable, match="rejected transaction"):
        fetch_jupiter_quote(
            TOKEN, "0.1", api_key="key", feed=FEED, request_get=transaction_response,
        )

    wrong_mint_response = Mock(return_value=_response({
        "outputMint": "So11111111111111111111111111111111111111112",
        "outAmount": "1", "transaction": None,
    }))
    with pytest.raises(JupiterQuoteUnavailable, match="output mint"):
        fetch_jupiter_quote(
            TOKEN, "0.1", api_key="key", feed=FEED, request_get=wrong_mint_response,
        )
