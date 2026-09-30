from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main
from presentation import dexsato_market_feed_token_presenter as presenter


TOKEN = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"


def _detail():
    return {
        "token_address": TOKEN,
        "symbol": "BONK",
        "dex_id": "raydium",
        "liquidity_usd": 123456.0,
    }


def test_universe_presenter_reuses_shell_and_binds_execution_api_base():
    shell = (
        "<title>BONK \u00b7 Solana Discovery</title>"
        '<a href="/discovery/solana/OTHER">Other</a>'
        f'<script>const c="/api/discovery/solana/{TOKEN}/candles";'
        f'const t="/api/discovery/solana/{TOKEN}/transactions";</script>'
        '<span class="eyebrow">Qualified exact-token workspace</span>'
        "<p>Review observed market activity, exact-pool identity and disclosed risk before taking any action.</p>"
        '<section class="qualification qualification-vp0d3"><div>qualification</div></section>'
        '<section class="discovery-engine-v12"><div>engine</div></section>'
        f'<section class="card jupiter jupiter-v27 trade-v04 trade-v05" data-jupiter-sandbox data-token-address="{TOKEN}">'
        "<div>trade</div></section>"
        '<section class="card market-snapshot-v26"><h3>Market Snapshot</h3></section>'
        "<h2>Token List</h2>"
        '<span class="token-list-chain-v07a">SOLANA</span>'
        '<div class="token-list-tabs-v07a" role="tablist" aria-label="Token list views"></div>'
    )

    with patch.object(presenter, "_render_market_token_shell", return_value=shell):
        html = presenter.render_solana_universe_token_page(
            _detail(),
            feed={"candidates": []},
        )

    assert f"/api/market/solana-universe/{TOKEN}/candles" in html
    assert f"/api/market/solana-universe/{TOKEN}/transactions" in html
    assert 'href="/market/solana-universe/OTHER"' in html
    assert "Solana Universe Workspace" in html
    assert "Solana Universe \u00b7 Core 20 workspace" in html
    assert "Solana Universe Context" in html
    assert "Core 20 \u00b7 Canonical Mint" in html
    assert "qualification" not in html
    assert ">engine<" not in html
    assert f'data-jupiter-sandbox data-api-base="/api/market/solana-universe/{TOKEN}"' in html
    assert "<h2>Solana Universe</h2>" in html
    assert ">CORE 20<" in html


def test_universe_workspace_route_reuses_adapter_and_presenter():
    detail = _detail()
    feed = {"candidates": [detail]}
    with (
        patch.object(
            main,
            "load_solana_universe_token_workspace",
            return_value=(detail, feed),
        ) as loader,
        patch.object(
            main,
            "render_solana_universe_token_page",
            return_value="UNIVERSE_WORKSPACE",
        ) as renderer,
    ):
        response = TestClient(main.app).get(
            f"/market/solana-universe/{TOKEN}"
        )

    assert response.status_code == 200
    assert "UNIVERSE_WORKSPACE" in response.text
    loader.assert_called_once_with(TOKEN)
    renderer.assert_called_once_with(detail, feed=feed)


def test_universe_workspace_route_returns_404_for_unresolved_token():
    with patch.object(
        main,
        "load_solana_universe_token_workspace",
        return_value=None,
    ):
        response = TestClient(main.app).get(
            "/market/solana-universe/not-core20"
        )
    assert response.status_code == 404


def test_universe_candle_route_binds_adapter_service():
    payload = {
        "token_address": TOKEN,
        "timeframe": "5m",
        "candles": [],
    }
    with patch.object(
        main,
        "load_solana_universe_live_candles",
        return_value=payload,
    ) as loader:
        response = TestClient(main.app).get(
            f"/api/market/solana-universe/{TOKEN}/candles?timeframe=5m"
        )

    assert response.status_code == 200
    assert response.json() == payload
    loader.assert_called_once_with(TOKEN, "5m")


def test_universe_transaction_route_binds_adapter_service():
    payload = {
        "token_address": TOKEN,
        "transactions": [],
    }
    with patch.object(
        main,
        "load_solana_universe_transactions",
        return_value=payload,
    ) as loader:
        response = TestClient(main.app).get(
            f"/api/market/solana-universe/{TOKEN}/transactions"
        )

    assert response.status_code == 200
    assert response.json() == payload
    loader.assert_called_once_with(TOKEN)

def _execution_feed():
    return {
        "candidates": [
            {
                "token_address": TOKEN,
                "pair_address": "PAIR",
                "symbol": "BONK",
            }
        ]
    }


def test_universe_jupiter_quote_uses_universe_execution_feed():
    feed = _execution_feed()
    quote = {"status": "QUOTE_READY", "token_address": TOKEN}
    with (
        patch.object(
            main,
            "load_solana_universe_execution_feed",
            return_value=feed,
        ),
        patch.object(
            main,
            "load_solana_universe_execution_record",
            return_value=feed["candidates"][0],
        ),
        patch(
            "application.jupiter_quote_service.fetch_jupiter_quote",
            return_value=quote,
        ) as fetch_quote,
    ):
        response = TestClient(main.app).get(
            f"/api/market/solana-universe/{TOKEN}/jupiter-quote"
            "?amount_sol=0.1&side=buy"
        )

    assert response.status_code == 200
    assert response.json() == quote
    fetch_quote.assert_called_once_with(
        TOKEN,
        "0.1",
        side="buy",
        feed=feed,
    )


def test_universe_execution_route_returns_404_without_eligible_feed_record():
    with (
        patch.object(
            main,
            "load_solana_universe_execution_feed",
            return_value={"candidates": []},
        ),
        patch.object(
            main,
            "load_solana_universe_execution_record",
            return_value=None,
        ),
    ):
        response = TestClient(main.app).get(
            f"/api/market/solana-universe/{TOKEN}/jupiter-quote"
        )

    assert response.status_code == 404


def test_universe_wallet_balance_uses_universe_record_loader():
    feed = _execution_feed()
    balance = {
        "status": "BALANCE_READY",
        "wallet_address": "wallet",
        "token_mint": TOKEN,
    }
    with (
        patch.object(
            main,
            "load_solana_universe_execution_feed",
            return_value=feed,
        ),
        patch.object(
            main,
            "load_solana_universe_execution_record",
            return_value=feed["candidates"][0],
        ),
        patch.object(
            main,
            "load_solana_wallet_balance",
            return_value=balance,
        ) as balance_loader,
    ):
        response = TestClient(main.app).get(
            f"/api/market/solana-universe/{TOKEN}/wallet-balance"
            "?wallet_address=wallet"
        )

    assert response.status_code == 200
    assert response.json() == balance
    args, kwargs = balance_loader.call_args
    assert args == (TOKEN, "wallet")
    assert callable(kwargs["record_loader"])
    assert kwargs["record_loader"](TOKEN) == feed["candidates"][0]


def test_universe_jupiter_order_passes_universe_feed_to_existing_swap_service():
    feed = _execution_feed()
    balance = {"status": "BALANCE_READY"}
    order = {"status": "ORDER_READY", "request_id": "request"}
    with (
        patch.object(
            main,
            "load_solana_universe_execution_feed",
            return_value=feed,
        ),
        patch.object(
            main,
            "load_solana_universe_execution_record",
            return_value=feed["candidates"][0],
        ),
        patch.object(
            main,
            "load_solana_wallet_balance",
            return_value=balance,
        ),
        patch.object(main, "validate_wallet_trade_amount") as validate,
        patch(
            "application.jupiter_swap_service.prepare_jupiter_swap",
            return_value=order,
        ) as prepare,
    ):
        response = TestClient(main.app).post(
            f"/api/market/solana-universe/{TOKEN}/jupiter-order",
            json={
                "amount_sol": "0.1",
                "side": "buy",
                "wallet_address": "wallet",
                "risk_acknowledged": True,
            },
        )

    assert response.status_code == 200
    assert response.json() == order
    validate.assert_called_once_with(balance, "buy", "0.1")
    prepare.assert_called_once_with(
        TOKEN,
        "0.1",
        "wallet",
        side="buy",
        risk_acknowledged=True,
        feed=feed,
    )


def test_universe_jupiter_execute_passes_universe_feed_to_existing_swap_service():
    feed = _execution_feed()
    executed = {"status": "EXECUTED"}
    with (
        patch.object(
            main,
            "load_solana_universe_execution_feed",
            return_value=feed,
        ),
        patch.object(
            main,
            "load_solana_universe_execution_record",
            return_value=feed["candidates"][0],
        ),
        patch(
            "application.jupiter_swap_service.execute_jupiter_swap",
            return_value=executed,
        ) as execute,
    ):
        response = TestClient(main.app).post(
            f"/api/market/solana-universe/{TOKEN}/jupiter-execute",
            json={
                "request_id": "request",
                "wallet_address": "wallet",
                "signed_transaction": "signed",
            },
        )

    assert response.status_code == 200
    assert response.json() == executed
    execute.assert_called_once_with(
        TOKEN,
        "request",
        "wallet",
        "signed",
        feed=feed,
    )