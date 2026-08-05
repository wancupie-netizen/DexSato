"""Grounded, non-predictive risk notes for DexSato markets."""

from __future__ import annotations


def _normalized_reasons(value: object) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {
        str(reason).strip().upper()
        for reason in value
        if str(reason).strip()
    }


def build_market_risk_note(
    *,
    asset_class: object = "crypto",
    reasons: object = None,
    market_state: object = None,
    daily_change_pct: object = None,
) -> str:
    """Build one cautious note using only verified market evidence."""
    normalized_asset = str(asset_class or "crypto").strip().lower()
    normalized_state = str(market_state or "").strip().upper()
    evidence = _normalized_reasons(reasons)

    if normalized_asset == "commodities":
        if normalized_state == "UPPER_RANGE":
            return (
                "Price is near the upper end of today's range. This indicates "
                "strength, but it may also increase the possibility of a "
                "pullback if momentum does not continue. Volume and liquidity "
                "confirmation are unavailable."
            )
        if normalized_state == "LOWER_RANGE":
            return (
                "Price is near the lower end of today's range. Downward "
                "pressure remains visible, although a short-term rebound is "
                "possible. Volume and liquidity confirmation are unavailable."
            )
        if normalized_state == "MID_RANGE":
            return (
                "Price is in the middle of today's range, where direction is "
                "not yet clearly established. Volume and liquidity "
                "confirmation are unavailable."
            )
        return (
            "Complete OHLC data is not yet available, so current market risk "
            "cannot be assessed reliably."
        )

    if "DISTRIBUTION" in evidence and "RISKY_ACTIVITY" in evidence:
        return (
            "Selling pressure is increasing while risky market activity is "
            "present. This combination may increase volatility and downside "
            "risk; wait for price and liquidity conditions to stabilise."
        )
    if "DISTRIBUTION" in evidence:
        return (
            "Selling pressure is increasing. Further downside remains possible "
            "until price momentum and liquidity show clear stabilisation."
        )
    if "WEAK_MOMENTUM" in evidence or "WEAK_BREAKOUT" in evidence:
        return (
            "Current momentum remains weak and direction is not fully "
            "confirmed. A failed continuation or reversal remains possible."
        )
    if evidence & {"MOMENTUM", "PRICE_MOMENTUM", "PRICE_BREAKOUT", "PRICE_UP"}:
        return (
            "Momentum is strengthening, but rapid price movement can increase "
            "volatility and the risk of a short-term pullback. Wait for "
            "continued price and liquidity confirmation."
        )
    if "RISKY_ACTIVITY" in evidence:
        return (
            "Risky market activity is present. Conditions may change quickly, "
            "so current evidence should be reviewed before any decision."
        )
    if "STRONG_LIQUIDITY" in evidence or "LIQUIDITY_UP" in evidence:
        return (
            "Liquidity is currently supportive, but liquidity alone does not "
            "confirm price direction or protect against a sudden reversal."
        )
    return (
        "Current evidence is limited and does not fully confirm market "
        "direction. Continue monitoring for material changes."
    )
