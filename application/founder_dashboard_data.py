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
from application.risk_note import build_market_risk_note


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

        reference_only = result.get(
            "reference_only",
            False,
        ) is True

        if reference_only and isinstance(market, dict):
            intelligence = result.get("reference_intelligence")
            if not isinstance(intelligence, dict):
                intelligence = {}
            serialized.append(
                {
                    "token": token,
                    "pair": market.get("pair"),
                    "price": market.get("price"),
                    "liquidity": market.get("liquidity"),
                    "volume_24h": market.get("volume_24h"),
                    "market_cap": market.get("market_cap"),
                    "fdv": market.get("fdv"),
                    "pair_address": market.get("pair_address"),
                    "chain": market.get("chain"),
                    "source": market.get("source"),
                    "scanned_at": market.get("scanned_at"),
                    "price_change_24h": market.get("price_change_24h"),
                    "trading_venues": [],
                    "trading_venues_status": "NOT_APPLICABLE",
                    "technical_evidence": {},
                    "technical_evidence_status": "NOT_APPLICABLE",
                    "fundamental_context": {},
                    "fundamental_context_status": "NOT_APPLICABLE",
                    "asset_class": "commodities",
                    "available": True,
                    "decision": "REFERENCE",
                    "confidence": "REFERENCE",
                    "historical_success": None,
                    "seen_before": False,
                    "reasons": [],
                    "market_state": intelligence.get("market_state"),
                    "daily_change_pct": intelligence.get("daily_change_pct"),
                    "intraday_range_pct": intelligence.get("intraday_range_pct"),
                    "range_position_pct": intelligence.get("range_position_pct"),
                    "reference_evidence": list(
                        intelligence.get("evidence", [])
                    ),
                    "summary": intelligence.get(
                        "summary",
                        "Gold reference intelligence is collecting data.",
                    ),
                    "risk_note": build_market_risk_note(
                        asset_class="commodities",
                        market_state=intelligence.get("market_state"),
                        daily_change_pct=intelligence.get("daily_change_pct"),
                    ),
                    "error": None,
                }
            )
            continue

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
                    "scanned_at": None,
                    "price_change_24h": None,
                    "trading_venues": [],
                    "trading_venues_status": "UNAVAILABLE",
                    "technical_evidence": {},
                    "technical_evidence_status": "UNAVAILABLE",
                    "fundamental_context": {},
                    "fundamental_context_status": "UNAVAILABLE",
                    "asset_class": None,
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
                "scanned_at": market.get("scanned_at"),
                "price_change_24h": market.get("price_change_24h"),
                "trading_venues": list(result.get("trading_venues", [])),
                "trading_venues_status": result.get(
                    "trading_venues_status",
                    "NOT_REQUESTED",
                ),
                "technical_evidence": dict(
                    result.get("technical_evidence", {})
                    if isinstance(result.get("technical_evidence"), dict)
                    else {}
                ),
                "technical_evidence_status": result.get(
                    "technical_evidence_status",
                    "NOT_REQUESTED",
                ),
                "fundamental_context": dict(
                    result.get("fundamental_context", {})
                    if isinstance(result.get("fundamental_context"), dict)
                    else {}
                ),
                "fundamental_context_status": result.get(
                    "fundamental_context_status", "NOT_REQUESTED"
                ),
                "asset_class": "crypto",
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
                "risk_note": build_market_risk_note(
                    asset_class="crypto",
                    reasons=list(card.reasons),
                ),
                "error": None,
            }
        )

    return serialized
