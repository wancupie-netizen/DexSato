from pathlib import Path

from presentation.dexsato_solana_discovery_token_presenter import render_solana_discovery_token_page


DETAIL = {
    "token_address": "TokenAddress123456789", "pair_address": "PoolAddress123456789",
    "symbol": "TEST", "name": "Test Token", "quote_symbol": "SOL",
    "dex_id": "raydium", "price_usd": .12, "change_24h": 4.5,
    "liquidity_usd": 7000, "volume_24h_usd": 3000, "market_cap": 120000,
    "pair_age": "2h", "quote_status": "LIVE", "quote_label": "Live exact-pool observation",
    "evidence": "Observed liquidity and activity.", "risk_label": "Security unavailable",
    "source_url": "https://dexscreener.com/solana/pool", "feed_updated_label": "4 min ago",
    "chart": [
        {"close": .10}, {"close": .11}, {"close": .105},
        {"close": .115}, {"close": .108}, {"close": .12},
    ],
}


def test_renders_exact_token_workspace_and_chart():
    html = render_solana_discovery_token_page(DETAIL)
    assert "Qualified exact-token workspace" in html
    assert "TEST / SOL" in html
    assert "Validated exact-pool data" in html
    assert "aria-label=\"Validated exact-pool 4H closing-price chart\"" in html
    assert "Live exact-pool observation" in html
    assert "Open market source" in html
    assert 'src="/static/branding/dexsato-logo.png"' in html
    assert 'data-copy-address="TokenAddress123456789"' in html
    assert 'data-copy-address="PoolAddress123456789"' in html


def test_renders_controlled_non_custodial_jupiter_swap_and_discloses_risk():
    html = render_solana_discovery_token_page(DETAIL)
    assert "Jupiter integration sandbox" in html
    assert "Controlled wallet-approved swap" in html
    assert "D6 · NON-CUSTODIAL PILOT" in html
    assert "Connect supported wallet" in html
    assert "Get Jupiter quote" in html
    assert "Real Solana mainnet transaction" in html
    assert "review the transaction in my own wallet" in html
    assert 'data-swap-risk-ack' in html
    assert 'data-execute-swap disabled' in html
    assert 'data-token-symbol="TEST"' in html
    assert 'src="/static/js/dexsato_solana_discovery_swap.js" defer' in html
    assert "DexSato integrator fee: <strong>0 bps</strong>" in html
    assert "Pool verification is not token verification" in html
    assert "does not hold private keys or funds" in html
    assert "Transactions must be approved in your connected wallet" in html
    assert html.index("Risk context") < html.index("Qualification evidence")
    assert html.index("Qualification evidence") < html.index("Jupiter integration sandbox")
    assert 'class="card jupiter" data-jupiter-sandbox' in html


def test_chart_fails_safely_when_unavailable():
    html = render_solana_discovery_token_page({**DETAIL, "chart": []})
    assert "Insufficient chart history" in html
    assert "Only 0 closed 4H candles available" in html


def test_swap_client_requires_explicit_wallet_signing_and_preserves_same_origin_api_keys():
    script = (
        Path(__file__).resolve().parents[1]
        / "static" / "js" / "dexsato_solana_discovery_swap.js"
    ).read_text(encoding="utf-8")

    assert "walletProvider.signTransaction(unsigned)" in script
    assert "VersionedTransaction.deserialize" in script
    assert 'apiBase + "/jupiter-order"' in script
    assert 'apiBase + "/jupiter-execute"' in script
    assert "risk_acknowledged: acknowledgement.checked" in script
    assert "Retry signed transaction" in script
    assert "credentials: \"same-origin\"" in script
    assert "x-api-key" not in script
    assert "privateKey" not in script and "seedPhrase" not in script


def test_chart_does_not_imply_a_trend_from_two_candles():
    html = render_solana_discovery_token_page({
        **DETAIL, "chart": [{"close": .12}, {"close": .08}],
    })

    assert "Only 2 closed 4H candles available" in html
    assert "At least 6 are required" in html
    assert "<polyline" not in html
