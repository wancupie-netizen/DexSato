"""Tests for commodity reference dashboard results."""

import requests

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
            },
            "provider_quote": {
                "open": "4000",
                "high": "4100",
                "low": "3950",
                "close": "4073.39",
                "previous_close": "4020",
            },
        }

    result = build_commodity_reference_results(scan=fake_scan)[0]

    assert result["token"] == "XAU"
    assert result["reference_only"] is True
    assert result["card"] is None
    assert result["market"]["pair"] == "XAU/USD"
    assert result["reference_intelligence"]["market_state"] == (
        "UPPER_RANGE"
    )


def test_provider_timeout_degrades_only_reference_market():
    def timed_out_scan(token):
        raise requests.ReadTimeout("Twelve Data timed out")

    result = build_commodity_reference_results(scan=timed_out_scan)[0]

    assert result["token"] == "XAU"
    assert result["reference_only"] is True
    assert result["market"] is None
    assert result["error"] == "Twelve Data timed out"
