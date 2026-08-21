"""Build non-actionable reference results for commodity markets."""

from __future__ import annotations

from collections.abc import Callable

from scanner.commodity_registry import load_commodity_registry
from scanner.commodity_runner import scan_commodity_market
from scanner.gold_intelligence import build_gold_reference_intelligence


def build_commodity_reference_results(
    *,
    scan: Callable[[str], dict] = scan_commodity_market,
) -> list[dict[str, object]]:
    """Scan registered commodities without issuing trade decisions."""
    results: list[dict[str, object]] = []

    for token in load_commodity_registry():
        try:
            scan_result = scan(token)
            event = scan_result["event"]
            intelligence = build_gold_reference_intelligence(
                scan_result.get("provider_quote", {})
            )
        except Exception as error:
            # Commodity reference data is optional. Provider timeouts or
            # adapter failures must not cancel the complete crypto snapshot.
            results.append({"token": token, "card": None, "market": None, "reference_only": True, "error": str(error)})
            continue

        results.append(
            {
                "token": token,
                "card": None,
                "market": event,
                "reference_only": True,
                "reference_intelligence": intelligence,
                "error": None,
            }
        )

    return results
