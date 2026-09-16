"""Stateless user-readable intelligence for DexSato market-feed tabs.

Mirrors canonical DexSato price/volume/liquidity interpretation semantics
against already-observed feed deltas, then adds transparent Jupiter 1h
buyer/seller and holder evidence.

This module never changes eligibility, ranking, Discovery state, or execution.
"""

from __future__ import annotations

from typing import Any


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


PRICE_NOISE_FLOOR_PCT = 0.5
VOLUME_NOISE_FLOOR_PCT = 5.0
LIQUIDITY_NOISE_FLOOR_PCT = 2.0
HOLDER_NOISE_FLOOR_PCT = 0.5


def _direction(value: Any, *, noise_floor: float = 0.0) -> str | None:
    number = _number(value)
    if number is None:
        return None
    if abs(number) < max(0.0, float(noise_floor)):
        return "STABLE"
    if number > 0:
        return "UP"
    if number < 0:
        return "DOWN"
    return "STABLE"


def _buy_pressure(stats: dict[str, Any]) -> bool:
    buy_volume = _number(stats.get("buyVolume"))
    sell_volume = _number(stats.get("sellVolume"))
    num_buys = _number(stats.get("numBuys"))
    num_sells = _number(stats.get("numSells"))
    net_buyers = _number(stats.get("numNetBuyers"))

    evidence = 0
    if buy_volume is not None and sell_volume is not None and buy_volume > sell_volume:
        evidence += 1
    if num_buys is not None and num_sells is not None and num_buys > num_sells:
        evidence += 1
    if net_buyers is not None and net_buyers > 0:
        evidence += 1
    return evidence >= 2


def _sell_pressure(stats: dict[str, Any]) -> bool:
    buy_volume = _number(stats.get("buyVolume"))
    sell_volume = _number(stats.get("sellVolume"))
    num_buys = _number(stats.get("numBuys"))
    num_sells = _number(stats.get("numSells"))
    net_buyers = _number(stats.get("numNetBuyers"))

    evidence = 0
    if buy_volume is not None and sell_volume is not None and sell_volume > buy_volume:
        evidence += 1
    if num_buys is not None and num_sells is not None and num_sells > num_buys:
        evidence += 1
    if net_buyers is not None and net_buyers < 0:
        evidence += 1
    return evidence >= 2


def _canonical_interpretation(
    *,
    price: str | None,
    volume: str | None,
    liquidity: str | None,
    buy_pressure: bool,
    sell_pressure: bool,
) -> tuple[str | None, str]:
    signals = {
        name
        for name in (
            f"PRICE_{price}" if price else None,
            f"VOLUME_{volume}" if volume else None,
            f"LIQUIDITY_{liquidity}" if liquidity else None,
        )
        if name
    }

    # Risk-sensitive conditions take precedence over bullish presentation.
    if {"LIQUIDITY_DOWN", "VOLUME_UP"}.issubset(signals):
        return "Volume rising while liquidity weakens", "mixed"
    if {"LIQUIDITY_DOWN", "PRICE_UP"}.issubset(signals):
        return "Price rising on weakening liquidity", "mixed"

    # Strong bullish wording requires aligned participation evidence.
    if {"PRICE_UP", "VOLUME_UP", "LIQUIDITY_UP"}.issubset(signals):
        if buy_pressure and not sell_pressure:
            return "Bullish pattern strengthening", "bullish"
        return "Bullish momentum developing", "bullish"

    if {"PRICE_UP", "VOLUME_UP"}.issubset(signals):
        return "Bullish momentum developing", "bullish"

    if {"PRICE_DOWN", "VOLUME_UP"}.issubset(signals):
        if sell_pressure and not buy_pressure:
            return "Bearish pressure developing", "bearish"
        return "Bearish pattern developing", "bearish"

    if {"PRICE_DOWN", "VOLUME_DOWN"}.issubset(signals):
        return "Momentum weakening", "bearish"
    if {"PRICE_UP", "VOLUME_DOWN"}.issubset(signals):
        return "Price rising but volume is weakening", "mixed"
    if {"PRICE_STABLE", "VOLUME_UP"}.issubset(signals):
        return "Buying interest building", "neutral"
    if {"PRICE_STABLE", "VOLUME_DOWN"}.issubset(signals):
        return "Market interest weakening", "neutral"
    if {"LIQUIDITY_UP", "VOLUME_UP"}.issubset(signals):
        return "Liquidity and volume expanding", "bullish"

    return None, "neutral"


def interpret_trending_signal(stats: dict[str, Any] | None) -> dict[str, Any]:
    data = stats if isinstance(stats, dict) else {}

    price = _direction(
        data.get("priceChange"),
        noise_floor=PRICE_NOISE_FLOOR_PCT,
    )
    volume = _direction(
        data.get("volumeChange"),
        noise_floor=VOLUME_NOISE_FLOOR_PCT,
    )
    liquidity = _direction(
        data.get("liquidityChange"),
        noise_floor=LIQUIDITY_NOISE_FLOOR_PCT,
    )
    holder = _direction(
        data.get("holderChange"),
        noise_floor=HOLDER_NOISE_FLOOR_PCT,
    )

    buy_pressure = _buy_pressure(data)
    sell_pressure = _sell_pressure(data)

    primary, direction = _canonical_interpretation(
        price=price,
        volume=volume,
        liquidity=liquidity,
        buy_pressure=buy_pressure,
        sell_pressure=sell_pressure,
    )

    if primary and direction == "bullish" and sell_pressure:
        primary, direction = "Mixed market signals", "mixed"
    elif primary and direction == "bearish" and buy_pressure:
        primary, direction = "Mixed market signals", "mixed"

    if primary is None:
        if buy_pressure and not sell_pressure:
            primary, direction = "Buying pressure increasing", "bullish"
        elif sell_pressure and not buy_pressure:
            primary, direction = "Selling pressure increasing", "bearish"
        elif volume == "UP":
            primary, direction = "Volume increasing", "neutral"
        elif holder == "UP":
            primary, direction = "Holder growth increasing", "neutral"
        elif holder == "DOWN":
            primary, direction = "Holder count declining", "neutral"
        else:
            primary, direction = "No clear directional signal", "neutral"

    evidence: list[str] = []

    def add(text: str) -> None:
        if text not in evidence and text != primary and len(evidence) < 2:
            evidence.append(text)

    if sell_pressure:
        add("Sell pressure ↑")
    elif buy_pressure:
        add("Buy pressure ↑")

    if volume == "UP":
        add("Volume ↑")
    elif volume == "DOWN":
        add("Volume ↓")

    if holder == "UP":
        add("Holders ↑")
    elif holder == "DOWN":
        add("Holders ↓")

    if liquidity == "DOWN":
        add("Liquidity ↓")
    elif liquidity == "UP":
        add("Liquidity ↑")

    return {
        "primary_signal": primary,
        "secondary_evidence": evidence,
        "direction": direction,
        "confidence_basis": len(evidence),
        "source": "JUPITER_1H + DEXSATO_RULES",
    }
