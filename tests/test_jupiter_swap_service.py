import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from application.jupiter_quote_service import (
    WRAPPED_SOL_MINT,
    JupiterQuoteNotConfigured,
    JupiterQuoteUnavailable,
)
from application.jupiter_swap_service import (
    JUPITER_EXECUTE_URL,
    JUPITER_ORDER_URL,
    JupiterSwapExpired,
    JupiterSwapRejected,
    _pending_orders,
    execute_jupiter_swap,
    prepare_jupiter_swap,
)


WALLET = "11111111111111111111111111111111"
TOKEN = "22222222222222222222222222222222"
OTHER_TOKEN = "33333333333333333333333333333333"
FEED = {"candidates": [{"token_address": TOKEN, "symbol": "TEST"}]}
NOW = datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)


def _transaction(signature=None, *, change_message=False):
    signer = bytes(32)
    recent_blockhash = bytes([7 if change_message else 6]) * 32
    message = bytes([128, 1, 0, 0, 1]) + signer + recent_blockhash + bytes([0, 0])
    transaction = bytes([1]) + (signature or bytes(64)) + message
    return base64.b64encode(transaction).decode("ascii")


def _response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def _order(request_id="order-test-1", **changes):
    payload = {
        "inputMint": WRAPPED_SOL_MINT,
        "outputMint": TOKEN,
        "inAmount": "100000000",
        "outAmount": "2500000",
        "otherAmountThreshold": "2450000",
        "router": "metis",
        "priceImpact": 0.12,
        "feeBps": 5,
        "taker": WALLET,
        "requestId": request_id,
        "transaction": _transaction(),
        "lastValidBlockHeight": "123456",
    }
    payload.update(changes)
    return payload


def _prepare(payload=None, **changes):
    return prepare_jupiter_swap(
        TOKEN,
        "0.1",
        WALLET,
        risk_acknowledged=True,
        api_key="server-secret",
        feed=FEED,
        request_get=Mock(return_value=_response(payload or _order())),
        now=lambda: NOW,
        **changes,
    )


def test_prepares_unsigned_order_bound_to_qualified_token_amount_and_wallet():
    _pending_orders.clear()
    request_get = Mock(return_value=_response(_order()))

    order = prepare_jupiter_swap(
        TOKEN, "0.1", WALLET, risk_acknowledged=True,
        api_key="server-secret", feed=FEED, request_get=request_get, now=lambda: NOW,
    )

    assert order["status"] == "WALLET_APPROVAL_REQUIRED"
    assert order["wallet_address"] == WALLET
    assert order["output_mint"] == TOKEN
    assert order["unsigned_transaction"] == _transaction()
    assert order["request_id"] == "order-test-1"
    assert order["dexsato_integrator_fee_bps"] == 0
    assert order["expires_at"] == (NOW + timedelta(seconds=120)).isoformat()
    assert "server-secret" not in str(order)
    call = request_get.call_args
    assert call.args[0] == JUPITER_ORDER_URL
    assert call.kwargs["params"] == {
        "inputMint": WRAPPED_SOL_MINT, "outputMint": TOKEN,
        "amount": "100000000", "taker": WALLET,
    }
    assert "referralFee" not in call.kwargs["params"]
    assert call.kwargs["headers"]["x-api-key"] == "server-secret"


def test_requires_explicit_risk_acknowledgement_before_requesting_order():
    _pending_orders.clear()
    request_get = Mock()
    with pytest.raises(JupiterSwapRejected, match="acknowledged"):
        prepare_jupiter_swap(
            TOKEN, "0.1", WALLET, risk_acknowledged=False,
            api_key="server-secret", feed=FEED, request_get=request_get,
        )
    request_get.assert_not_called()


def test_rejects_unknown_token_invalid_wallet_and_out_of_range_amount():
    _pending_orders.clear()
    with pytest.raises(JupiterSwapRejected, match="qualified"):
        prepare_jupiter_swap(
            OTHER_TOKEN, "0.1", WALLET, risk_acknowledged=True,
            api_key="key", feed=FEED,
        )
    with pytest.raises(JupiterSwapRejected, match="wallet"):
        prepare_jupiter_swap(
            TOKEN, "0.1", "invalid-wallet", risk_acknowledged=True,
            api_key="key", feed=FEED,
        )
    with pytest.raises(ValueError, match="between"):
        prepare_jupiter_swap(
            TOKEN, "101", WALLET, risk_acknowledged=True,
            api_key="key", feed=FEED,
        )


def test_requires_server_side_jupiter_api_key():
    _pending_orders.clear()
    with pytest.raises(JupiterQuoteNotConfigured):
        prepare_jupiter_swap(
            TOKEN, "0.1", WALLET, risk_acknowledged=True,
            api_key="", feed=FEED,
        )


def test_surfaces_insufficient_sol_balance_as_actionable_message():
    _pending_orders.clear()
    payload = _order(
        transaction="",
        error="Insufficient funds",
        errorMessage="Insufficient funds",
    )
    with pytest.raises(JupiterQuoteUnavailable, match="Insufficient SOL balance"):
        _prepare(payload)


def test_rejects_provider_token_wallet_amount_and_transaction_mismatches():
    cases = [
        ({"outputMint": OTHER_TOKEN}, "output mint"),
        ({"inputMint": TOKEN}, "input mint"),
        ({"inAmount": "1"}, "input amount"),
        ({"taker": OTHER_TOKEN}, "wallet"),
        ({"transaction": "not-base64"}, "base64"),
        ({"transaction": _transaction(bytes([9]) * 64)}, "already-signed"),
        ({"requestId": "../unsafe"}, "identifier"),
    ]
    for changes, expected in cases:
        _pending_orders.clear()
        with pytest.raises(JupiterSwapRejected, match=expected):
            _prepare(_order(**changes))


def test_uses_shorter_provider_expiration_and_rejects_expired_order():
    _pending_orders.clear()
    provider_expiry = NOW + timedelta(seconds=30)
    order = _prepare(_order(expireAt=provider_expiry.isoformat()))
    assert order["expires_at"] == provider_expiry.isoformat()

    _pending_orders.clear()
    with pytest.raises(JupiterSwapExpired, match="expired"):
        _prepare(_order(expireAt=(NOW - timedelta(seconds=1)).isoformat()))


def test_executes_only_the_wallet_signed_unchanged_transaction():
    _pending_orders.clear()
    order = _prepare()
    signed = _transaction(bytes([9]) * 64)
    request_post = Mock(return_value=_response({
        "status": "Success", "signature": "5" * 88, "slot": "987",
        "inputAmountResult": "100000000", "outputAmountResult": "2480000",
    }))

    result = execute_jupiter_swap(
        TOKEN, order["request_id"], WALLET, signed,
        api_key="server-secret", feed=FEED, request_post=request_post,
        now=lambda: NOW + timedelta(seconds=10),
    )

    assert result["status"] == "SWAP_CONFIRMED"
    assert result["signature"] == "5" * 88
    assert result["output_amount_raw"] == "2480000"
    assert result["dexsato_integrator_fee_bps"] == 0
    call = request_post.call_args
    assert call.args[0] == JUPITER_EXECUTE_URL
    assert call.kwargs["json"] == {
        "signedTransaction": signed,
        "requestId": order["request_id"],
        "lastValidBlockHeight": "123456",
    }
    assert call.kwargs["headers"]["x-api-key"] == "server-secret"


def test_rejects_unsigned_modified_expired_or_replayed_transactions():
    _pending_orders.clear()
    order = _prepare()
    post = Mock()
    with pytest.raises(JupiterSwapRejected, match="not signed"):
        execute_jupiter_swap(
            TOKEN, order["request_id"], WALLET, _transaction(),
            api_key="key", feed=FEED, request_post=post, now=lambda: NOW,
        )
    with pytest.raises(JupiterSwapRejected, match="changed"):
        execute_jupiter_swap(
            TOKEN, order["request_id"], WALLET,
            _transaction(bytes([8]) * 64, change_message=True),
            api_key="key", feed=FEED, request_post=post, now=lambda: NOW,
        )
    with pytest.raises(JupiterSwapExpired, match="expired"):
        execute_jupiter_swap(
            TOKEN, order["request_id"], WALLET, _transaction(bytes([8]) * 64),
            api_key="key", feed=FEED, request_post=post,
            now=lambda: NOW + timedelta(seconds=121),
        )
    post.assert_not_called()


def test_retry_must_reuse_exactly_the_same_wallet_signed_transaction():
    _pending_orders.clear()
    order = _prepare()
    signed = _transaction(bytes([4]) * 64)
    unavailable = Mock(side_effect=RuntimeError("provider timeout"))
    with pytest.raises(JupiterQuoteUnavailable, match="temporarily unavailable"):
        execute_jupiter_swap(
            TOKEN, order["request_id"], WALLET, signed,
            api_key="key", feed=FEED, request_post=unavailable, now=lambda: NOW,
        )

    with pytest.raises(JupiterSwapRejected, match="cannot replace"):
        execute_jupiter_swap(
            TOKEN, order["request_id"], WALLET, _transaction(bytes([5]) * 64),
            api_key="key", feed=FEED, request_post=Mock(), now=lambda: NOW,
        )

    recovered = Mock(return_value=_response({"status": "Success", "signature": "6" * 88}))
    result = execute_jupiter_swap(
        TOKEN, order["request_id"], WALLET, signed,
        api_key="key", feed=FEED, request_post=recovered, now=lambda: NOW,
    )
    assert result["status"] == "SWAP_CONFIRMED"

    with pytest.raises(JupiterSwapExpired, match="unavailable"):
        execute_jupiter_swap(
            TOKEN, order["request_id"], WALLET, signed,
            api_key="key", feed=FEED, request_post=recovered, now=lambda: NOW,
        )


def test_provider_failure_is_reported_without_exposing_secrets():
    _pending_orders.clear()
    order = _prepare()
    failed = Mock(return_value=_response({
        "status": "Failed", "error": "Slippage tolerance exceeded", "code": 6001,
    }))
    result = execute_jupiter_swap(
        TOKEN, order["request_id"], WALLET, _transaction(bytes([3]) * 64),
        api_key="server-secret", feed=FEED, request_post=failed, now=lambda: NOW,
    )
    assert result == {
        "status": "SWAP_FAILED", "request_id": order["request_id"],
        "error": "Slippage tolerance exceeded", "code": 6001,
        "dexsato_integrator_fee_bps": 0,
    }


def test_rejects_a_second_submission_while_the_same_transaction_is_in_flight():
    _pending_orders.clear()
    order = _prepare()
    signed = _transaction(bytes([6]) * 64)

    def submit_once(*_args, **_kwargs):
        with pytest.raises(JupiterSwapRejected, match="already being submitted"):
            execute_jupiter_swap(
                TOKEN, order["request_id"], WALLET, signed,
                api_key="key", feed=FEED, request_post=Mock(), now=lambda: NOW,
            )
        return _response({"status": "Success", "signature": "7" * 88})

    result = execute_jupiter_swap(
        TOKEN, order["request_id"], WALLET, signed,
        api_key="key", feed=FEED, request_post=submit_once, now=lambda: NOW,
    )
    assert result["status"] == "SWAP_CONFIRMED"
