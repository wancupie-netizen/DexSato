"""Tests for grounded market Risk Notes."""

from application.risk_note import build_market_risk_note


def test_should_describe_crypto_distribution_risk():
    note = build_market_risk_note(
        reasons=["DISTRIBUTION", "RISKY_ACTIVITY"],
    )
    assert "Selling pressure is increasing" in note
    assert "downside risk" in note


def test_should_describe_crypto_momentum_risk():
    note = build_market_risk_note(
        reasons=["PRICE_MOMENTUM", "STRONG_LIQUIDITY"],
    )
    assert "short-term pullback" in note


def test_should_describe_gold_upper_range_risk():
    note = build_market_risk_note(
        asset_class="commodities",
        market_state="UPPER_RANGE",
    )
    assert "upper end of today's range" in note
    assert "liquidity confirmation are unavailable" in note
