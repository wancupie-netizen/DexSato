"""Tests for commodity reference dashboard results."""

from application.commodity_dashboard_service import (
    build_commodity_reference_results,
)


def test_should_build_non_actionable_gold_reference():
    def fake_scan(token):
        assert token == "XAU"
        return {
            "event": {
                "token": "XAU",
                "pair": "XAU/USD",
                "price": "4073.39",
                "liquidity": None,
                "volume_24h": None,
                "market_cap": None,
                "fdv": None,
                "pair_address": "twelvedata:XAU/USD",
                "chain": "spot-metals",
                "source": "Twelve Data",
            }
        }

    result = build_commodity_reference_results(scan=fake_scan)[0]

    assert result["token"] == "XAU"
    assert result["reference_only"] is True
    assert result["card"] is None
    assert result["market"]["pair"] == "XAU/USD"
