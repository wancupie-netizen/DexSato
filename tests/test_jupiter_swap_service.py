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
    COMPUTE_BUDGET_PROGRAM,
    JUPITER_V6_PROGRAM,
    PHANTOM_LIGHTHOUSE_PROGRAM,
    SYSTEM_PROGRAM,
    MAX_PENDING_ORDERS_PER_WALLET,
    JUPITER_EXECUTE_URL,
    JUPITER_ORDER_URL,
    JupiterSwapExpired,
    JupiterSwapRejected,
    _pending_orders,
    _base58_bytes,
    _CompiledInstruction,
    _transaction_parts,
    _validate_lighthouse_augmentation,
    _validate_transaction_policy,
    execute_jupiter_swap,
    prepare_jupiter_swap,
)


WALLET = "11111111111111111111111111111111"
TOKEN = "22222222222222222222222222222222"
OTHER_TOKEN = "33333333333333333333333333333333"
UNAPPROVED_PROGRAM = "Vote111111111111111111111111111111111111111"
FEED = {
    "candidates": [
        {"token_address": TOKEN, "symbol": "TEST", "currently_qualified": True}
    ]
}
NOW = datetime(2026, 8, 23, 8, 0, tzinfo=timezone.utc)


def _transaction(
    signature=None,
    *,
    change_message=False,
    program=JUPITER_V6_PROGRAM,
    include_wallet=True,
    extra_signer=False,
):
    signer = bytes(32)
    other_signer = bytes([3]) * 32
    program_bytes = _base58_bytes(program)
    recent_blockhash = bytes([7 if change_message else 6]) * 32
    signer_count = 2 if extra_signer else 1
    accounts = signer + (other_signer if extra_signer else b"") + program_bytes
    program_index = signer_count
    instruction_accounts = bytes([0]) if include_wallet else bytes([program_index])
    message = (
        bytes([128, signer_count, 0, 1, signer_count + 1])
        + accounts
        + recent_blockhash
        + bytes([1, program_index, 1])
        + instruction_accounts
        + bytes([1, 1, 0])
    )
    signatures = (signature or bytes(64)) + (bytes(64) if extra_signer else b"")
    transaction = bytes([signer_count]) + signatures + message
    return base64.b64encode(transaction).decode("ascii")


def _versioned_transaction(
    signature: bytes,
    static_accounts: list[bytes],
    readonly_unsigned: int,
    instructions: list[tuple[int, tuple[int, ...], bytes]],
    lookups: list[tuple[bytes, tuple[int, ...], tuple[int, ...]]],
    *,
    blockhash: bytes | None = None,
) -> str:
    message = bytearray([128, 1, 0, readonly_unsigned, len(static_accounts)])
    message.extend(b"".join(static_accounts))
    message.extend(blockhash or bytes([6]) * 32)
    message.append(len(instructions))
    for program_index, account_indices, data in instructions:
        message.extend((program_index, len(account_indices), *account_indices, len(data)))
        message.extend(data)
    message.append(len(lookups))
    for table_account, writable_indexes, readonly_indexes in lookups:
        message.extend(table_account)
        message.extend((len(writable_indexes), *writable_indexes))
        message.extend((len(readonly_indexes), *readonly_indexes))
    return base64.b64encode(bytes([1]) + signature + bytes(message)).decode("ascii")


def _lighthouse_pair(
    *,
    core_data=b"\x01",
    signed_core_data=None,
    second_discriminator=10,
    signed_blockhash=None,
):
    wallet = _base58_bytes(WALLET)
    output_account = bytes([3]) * 32
    jupiter = _base58_bytes(JUPITER_V6_PROGRAM)
    lighthouse = _base58_bytes(PHANTOM_LIGHTHOUSE_PROGRAM)
    table_one = bytes([21]) * 32
    table_two = bytes([22]) * 32
    original = _versioned_transaction(
        bytes(64),
        [wallet, output_account, jupiter],
        1,
        [(2, (0,), core_data)],
        [
            (table_one, (141, 123), (117, 99)),
            (table_two, (62,), (52,)),
        ],
    )
    first_assertion = bytes.fromhex(
        "060403000dd98201000000000403000001000000000000000000"
    )
    second_assertion = bytes([second_discriminator]) + bytes(16)
    signed = _versioned_transaction(
        bytes([9]) * 64,
        [wallet, output_account, lighthouse, jupiter],
        2,
        [
            (3, (0,), core_data if signed_core_data is None else signed_core_data),
            (2, (0,), first_assertion),
            (2, (1,), second_assertion),
        ],
        [
            (table_one, (123, 141), (99, 117)),
            (table_two, (62,), (52,)),
        ],
        blockhash=signed_blockhash,
    )
    return original, signed


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


def _prepare_sell(payload=None, **changes):
    sell_order = _order(
        request_id="sell-order-1",
        inputMint=TOKEN,
        outputMint=WRAPPED_SOL_MINT,
        inAmount="1500000",
        outAmount="123000000",
        otherAmountThreshold="120000000",
        outputDecimals=9,
    )
    rpc = Mock(return_value=_response({
        "jsonrpc": "2.0",
        "result": {"value": {"amount": "1", "decimals": 6}},
    }))
    return prepare_jupiter_swap(
        TOKEN,
        "1.5",
        WALLET,
        side="sell",
        risk_acknowledged=True,
        api_key="server-secret",
        feed=FEED,
        request_get=Mock(return_value=_response(payload or sell_order)),
        request_post=rpc,
        now=lambda: NOW,
        **changes,
    )


def test_prepares_unsigned_order_bound_to_observed_token_amount_and_wallet():
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
        "excludeRouters": "jupiterz,dflow,okx",
    }
    assert "referralFee" not in call.kwargs["params"]
    assert call.kwargs["headers"]["x-api-key"] == "server-secret"


def test_prepares_sell_order_bound_to_direction_token_units_and_wallet():
    _pending_orders.clear()

    order = _prepare_sell()

    assert order["status"] == "WALLET_APPROVAL_REQUIRED"
    assert order["side"] == "sell"
    assert order["token_mint"] == TOKEN
    assert order["input_mint"] == TOKEN
    assert order["output_mint"] == WRAPPED_SOL_MINT
    assert order["input_amount_ui"] == "1.5"
    assert order["input_amount_raw"] == "1500000"
    assert order["input_decimals"] == 6
    assert order["output_amount_ui"] == "0.123"
    pending = _pending_orders[order["request_id"]]
    assert pending.side == "sell"
    assert pending.input_mint == TOKEN
    assert pending.output_mint == WRAPPED_SOL_MINT
    assert pending.input_amount_raw == "1500000"


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
    with pytest.raises(JupiterSwapRejected, match="observed"):
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


def test_allows_historical_observation_without_current_qualification():
    historical = {
        "candidates": [
            {"token_address": TOKEN, "symbol": "TEST", "currently_qualified": False}
        ]
    }
    _pending_orders.clear()
    order = prepare_jupiter_swap(
        TOKEN,
        "0.1",
        WALLET,
        risk_acknowledged=True,
        api_key="key",
        feed=historical,
        request_get=Mock(return_value=_response(_order(request_id="archive-order"))),
        now=lambda: NOW,
    )
    assert order["status"] == "WALLET_APPROVAL_REQUIRED"
    assert order["output_mint"] == TOKEN


def test_rejects_extra_signer_unapproved_program_and_missing_wallet_authority():
    cases = [
        ({"transaction": _transaction(extra_signer=True)}, "sole transaction signer"),
        ({"transaction": _transaction(program=UNAPPROVED_PROGRAM)}, "program that is not allowed"),
        ({"transaction": _transaction(program=COMPUTE_BUDGET_PROGRAM)}, "approved Jupiter program"),
        ({"transaction": _transaction(include_wallet=False)}, "not authorized"),
    ]
    for index, (changes, expected) in enumerate(cases):
        _pending_orders.clear()
        with pytest.raises(JupiterSwapRejected, match=expected):
            _prepare(_order(request_id=f"policy-{index}", **changes))


def test_rejects_cumulative_system_transfers_above_approved_sol_amount():
    wallet = _base58_bytes(WALLET)
    static_accounts = [
        wallet,
        _base58_bytes(SYSTEM_PROGRAM),
        _base58_bytes(JUPITER_V6_PROGRAM),
    ]
    transfer = (2).to_bytes(4, "little") + (60_000_000).to_bytes(8, "little")
    instructions = [
        _CompiledInstruction(1, (0, 1), transfer),
        _CompiledInstruction(1, (0, 1), transfer),
        _CompiledInstruction(2, (0,), b"\x01"),
    ]

    with pytest.raises(JupiterSwapRejected, match="exceeds"):
        _validate_transaction_policy(
            [wallet], static_accounts, instructions, wallet, 100_000_000
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


def test_one_wallet_cannot_fill_the_global_pending_order_store():
    _pending_orders.clear()
    for index in range(MAX_PENDING_ORDERS_PER_WALLET):
        order = _prepare(_order(request_id=f"wallet-quota-{index}"))
        assert order["status"] == "WALLET_APPROVAL_REQUIRED"

    with pytest.raises(JupiterQuoteUnavailable, match="too many pending swap reviews"):
        _prepare(_order(request_id="wallet-quota-overflow"))

    assert len(_pending_orders) == MAX_PENDING_ORDERS_PER_WALLET


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


def test_executes_phantom_lighthouse_augmented_transaction_without_weakening_core_order():
    _pending_orders.clear()
    original, signed = _lighthouse_pair()
    order = _prepare(_order(request_id="lighthouse-order", transaction=original))
    request_post = Mock(return_value=_response({
        "status": "Success", "signature": "7" * 88,
    }))

    result = execute_jupiter_swap(
        TOKEN, order["request_id"], WALLET, signed,
        api_key="server-secret", feed=FEED, request_post=request_post,
        now=lambda: NOW + timedelta(seconds=10),
    )

    assert result["status"] == "SWAP_CONFIRMED"
    assert request_post.call_args.kwargs["json"]["signedTransaction"] == signed


def test_lighthouse_execution_consumes_one_shot_gate_with_approved_message(tmp_path):
    import hashlib
    import json
    _pending_orders.clear()
    original, signed = _lighthouse_pair()
    order = _prepare(_order(request_id="lighthouse-gate", transaction=original))
    pending = _pending_orders[order["request_id"]]
    gate_path = tmp_path / "gate.json"
    gate_path.write_text(json.dumps({
        "status": "BOUND",
        "request_id": order["request_id"],
        "message_sha256": hashlib.sha256(pending.approved_message).hexdigest(),
    }), encoding="utf-8")
    pending.one_shot_gate_path = str(gate_path)

    execute_jupiter_swap(
        TOKEN, order["request_id"], WALLET, signed,
        api_key="server-secret", feed=FEED,
        request_post=Mock(return_value=_response({
            "status": "Success", "signature": "7" * 88,
        })),
        now=lambda: NOW + timedelta(seconds=10),
    )

    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    assert gate["status"] == "FINALIZATION_PENDING"
    assert gate["message_sha256"] == hashlib.sha256(pending.approved_message).hexdigest()


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"signed_core_data": b"\x02"}, "Jupiter instruction"),
        ({"second_discriminator": 11}, "unsupported Lighthouse"),
        ({"signed_blockhash": bytes([8]) * 32}, "blockhash"),
    ],
)
def test_rejects_lighthouse_wrapper_that_changes_approved_semantics(changes, expected):
    original, signed = _lighthouse_pair(**changes)
    _, _, approved_message, _, _, _ = _transaction_parts(original)
    _, _, signed_message, _, _, _ = _transaction_parts(signed)

    with pytest.raises(JupiterSwapRejected, match=expected):
        _validate_lighthouse_augmentation(
            approved_message,
            signed_message,
            _base58_bytes(WALLET),
        )


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
        "side": "buy",
        "error": "Slippage tolerance exceeded", "code": 6001,
        "dexsato_integrator_fee_bps": 0,
    }


def test_executes_sell_only_from_the_bound_pending_order():
    _pending_orders.clear()
    order = _prepare_sell()
    signed = _transaction(bytes([9]) * 64)
    request_post = Mock(return_value=_response({
        "status": "Success",
        "signature": "8" * 88,
        "inputAmountResult": "1500000",
        "outputAmountResult": "122000000",
    }))

    result = execute_jupiter_swap(
        TOKEN, order["request_id"], WALLET, signed,
        api_key="server-secret", feed=FEED, request_post=request_post,
        now=lambda: NOW + timedelta(seconds=10),
    )

    assert result["status"] == "SWAP_CONFIRMED"
    assert result["side"] == "sell"
    assert result["input_mint"] == TOKEN
    assert result["output_mint"] == WRAPPED_SOL_MINT
    assert result["input_amount_raw"] == "1500000"
    assert result["output_amount_raw"] == "122000000"


def test_sell_transaction_rejects_any_native_sol_transfer_from_wallet():
    wallet = _base58_bytes(WALLET)
    static_accounts = [wallet, _base58_bytes(SYSTEM_PROGRAM), _base58_bytes(JUPITER_V6_PROGRAM)]
    transfer = (2).to_bytes(4, "little") + (1).to_bytes(8, "little")
    instructions = [
        _CompiledInstruction(1, (0, 1), transfer),
        _CompiledInstruction(2, (0,), b"\x01"),
    ]

    with pytest.raises(JupiterSwapRejected, match="exceeds"):
        _validate_transaction_policy(
            [wallet], static_accounts, instructions, wallet, 0,
        )


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
