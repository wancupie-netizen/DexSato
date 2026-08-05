"""Build non-actionable reference results for commodity markets."""

from __future__ import annotations

from collections.abc import Callable

from scanner.commodity_registry import load_commodity_registry
from scanner.commodity_runner import scan_commodity_market


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
        except (RuntimeError, ValueError) as error:
            results.append({"token": token, "card": None, "market": None, "reference_only": True, "error": str(error)})
            continue

        results.append({"token": token, "card": None, "market": event, "reference_only": True, "error": None})

    return results
