from unittest.mock import Mock
from pathlib import Path

import pytest

from application.solana_wallet_balance_service import (
    TOKEN_PROGRAM,
    SolanaWalletBalanceRejected,
    load_solana_wallet_balance,
    validate_wallet_trade_amount,
)


WALLET = "11111111111111111111111111111111"
TOKEN = "22222222222222222222222222222222"


def _response(sol_value, token_value, sol_slot=100, token_slot=101):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [
        {"jsonrpc": "2.0", "id": "token", "result": {
            "context": {"slot": token_slot}, "value": token_value,
        }},
        {"jsonrpc": "2.0", "id": "sol", "result": {
            "context": {"slot": sol_slot}, "value": sol_value,
        }},
    ]
    return response


def _account(raw="1234567", decimals=6):
    return {
        "account": {
            "owner": TOKEN_PROGRAM,
            "data": {"parsed": {"info": {
                "mint": TOKEN,
                "owner": WALLET,
                "tokenAmount": {"amount": raw, "decimals": decimals},
            }}},
        }
    }


def test_returns_raw_spendable_sol_and_exact_token_balance():
    request_post = Mock(return_value=_response(2_005_000_000, [_account()]))

    result = load_solana_wallet_balance(
        TOKEN, WALLET, request_post=request_post, record_loader=lambda _token: {"observed": True},
    )

    assert result["sol_balance_lamports"] == "2005000000"
    assert result["buy_spendable_lamports"] == "2000000000"
    assert result["buy_spendable_ui"] == "2"
    assert result["token_balance_raw"] == "1234567"
    assert result["token_balance_ui"] == "1.234567"
    assert result["token_decimals"] == 6
    assert result["sell_percentage_ready"] is True
    assert result["slot"] == 101
    batch = request_post.call_args.kwargs["json"]
    assert [request["method"] for request in batch] == ["getBalance", "getTokenAccountsByOwner"]


def test_disables_sell_percentage_when_multiple_nonzero_token_accounts_exist():
    request_post = Mock(return_value=_response(
        10_000_000, [_account("100"), _account("200")],
    ))

    result = load_solana_wallet_balance(
        TOKEN, WALLET, request_post=request_post, record_loader=lambda _token: {"observed": True},
    )

    assert result["token_total_balance_raw"] == "300"
    assert result["token_balance_raw"] is None
    assert result["sell_percentage_ready"] is False


def test_rejects_amounts_above_latest_spendable_balance():
    balance = {
        "buy_spendable_lamports": "100000000",
        "token_total_balance_raw": "1500000",
        "token_decimals": 6,
    }

    validate_wallet_trade_amount(balance, "buy", "0.1")
    validate_wallet_trade_amount(balance, "sell", "1.5")
    with pytest.raises(SolanaWalletBalanceRejected, match="Insufficient spendable SOL"):
        validate_wallet_trade_amount(balance, "buy", "0.100000001")
    with pytest.raises(SolanaWalletBalanceRejected, match="Insufficient token balance"):
        validate_wallet_trade_amount(balance, "sell", "1.500001")


def test_app_routes_balance_read_and_rechecks_before_preparing_order():
    source = (
        Path(__file__).resolve().parents[1] / "app" / "main.py"
    ).read_text(encoding="utf-8")

    assert '@app.get("/api/discovery/solana/{token_address}/wallet-balance")' in source
    order_start = source.index(
        '@app.post("/api/discovery/solana/{token_address}/jupiter-order")'
    )
    execute_start = source.index(
        '@app.post("/api/discovery/solana/{token_address}/jupiter-execute")'
    )
    order_source = source[order_start:execute_start]
    assert order_source.index("load_solana_wallet_balance") < order_source.index(
        "validate_wallet_trade_amount"
    ) < order_source.rindex("prepare_jupiter_swap")
