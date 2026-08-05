"""Tests for isolated commodity ingestion."""

from scanner.commodity_runner import scan_commodity_market


QUOTE = {
    "symbol": "XAU/USD",
    "close": "4073.84",
    "open": "4077.53",
    "high": "4086.05",
    "low": "4065.90",
}


def test_should_persist_exact_gold_market_event():
    saved = []
    observed = {}

    def fake_fetch(market):
        assert market["provider_symbol"] == "XAU/USD"
        return QUOTE

    def fake_save(event):
        saved.append(event)

    def fake_observe(token, *, pair_address):
        observed.update(
            token=token,
            pair_address=pair_address,
        )
        return None

    result = scan_commodity_market(
        "xau",
        fetch=fake_fetch,
        save=fake_save,
        observe=fake_observe,
    )

    assert result["first_scan"] is True
    assert result["event"]["pair"] == "XAU/USD"
    assert result["event"]["price"] == "4073.84"
    assert result["event"]["liquidity"] is None
    assert result["provider_quote"] == QUOTE
    assert saved == [result["event"]]
    assert observed == {
        "token": "XAU",
        "pair_address": "twelvedata:XAU/USD",
    }


def test_should_return_pair_specific_observation():
    expected = {
        "token": "XAU",
        "price_change_pct": 0.25,
        "liquidity_change_pct": None,
        "volume_change_pct": None,
        "market_cap_change_pct": None,
        "fdv_change_pct": None,
    }

    def fake_observe(token, *, pair_address):
        assert token == "XAU"
        assert pair_address == "twelvedata:XAU/USD"
        return expected

    result = scan_commodity_market(
        "XAU",
        fetch=lambda market: QUOTE,
        save=lambda event: None,
        observe=fake_observe,
    )

    assert result["first_scan"] is False
    assert result["observation"] == expected
