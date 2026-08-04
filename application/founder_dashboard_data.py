"""
DexSato Founder Dashboard Shared Data.

Converts Founder Dashboard scan results into a small,
serializable data structure shared by the API and Telegram.

This module does NOT:
- run market scans
- render HTML
- send Telegram messages
- access persistence directly
"""

from __future__ import annotations

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
)


def serialize_founder_dashboard_results(
    results: list[dict[str, object]],
) -> list[dict[str, object]]:
    """
    Convert Founder Dashboard results into JSON-safe data.
    """

    if not isinstance(
        results,
        list,
    ):
        raise ValueError(
            "Founder dashboard results must be a list."
        )

    serialized: list[dict[str, object]] = []

    for result in results:

        token = str(
            result.get(
                "token",
                "UNKNOWN",
            )
        )

        card = result.get(
            "card",
        )

        error = result.get(
            "error",
        )

        market = result.get(
            "market",
        )

        if card is None:

            serialized.append(
                {
                    "token": token,
                    "pair": None,
                    "price": None,
                    "liquidity": None,
                    "volume_24h": None,
                    "market_cap": None,
                    "fdv": None,
                    "pair_address": None,
                    "chain": None,
                    "source": None,
                    "available": False,
                    "decision": None,
                    "confidence": None,
                    "historical_success": None,
                    "seen_before": False,
                    "reasons": [],
                    "summary": None,
                    "error": (
                        str(error)
                        if error is not None
                        else "Dashboard unavailable."
                    ),
                }
            )

            continue

        if not isinstance(
            card,
            DashboardCard,
        ):
            raise ValueError(
                "Founder dashboard result contains "
                "an invalid DashboardCard."
            )

        if not isinstance(
            market,
            dict,
        ):
            market = {}

        serialized.append(
            {
                "token": card.token,
                "pair": market.get("pair"),
                "price": market.get("price"),
                "liquidity": market.get("liquidity"),
                "volume_24h": market.get("volume_24h"),
                "market_cap": market.get("market_cap"),
                "fdv": market.get("fdv"),
                "pair_address": market.get("pair_address"),
                "chain": market.get("chain"),
                "source": market.get("source"),
                "available": True,
                "decision": card.decision,
                "confidence": card.confidence,
                "historical_success": (
                    card.historical_success
                ),
                "seen_before": card.seen_before,
                "reasons": list(
                    card.reasons,
                ),
                "summary": card.summary,
                "error": None,
            }
        )

    return serialized
