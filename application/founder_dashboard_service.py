"""
DexSato Founder Dashboard Service.

Runs the existing DexSato engine sequentially for the
approved V1 active market universe.

V1 Active Markets
-----------------
- BTC
- ETH
- SOL
- XRP
- SUI

Responsibilities
----------------
- Define the stable V1 production universe
- Run one production scan per valid token
- Preserve token ordering
- Preserve failed or unsupported-token information
- Continue scanning after individual token failures

This module does NOT:
- fetch the CoinMarketCap Top 100
- render HTML
- start FastAPI
- use threading
- send Telegram alerts
- schedule scans
- retry scans automatically
"""

from __future__ import annotations

from collections.abc import (
    Callable,
    Iterable,
)

from presentation.live_dashboard import (
    extract_dashboard,
    normalize_token,
)

from scanner.runner import (
    run_scan,
)


# ==========================================================
# V1 Active Production Universe
# ==========================================================

V1_ACTIVE_TOKENS = (
    "BTC",
    "ETH",
    "SOL",
    "XRP",
    "SUI",
)


# Backward-compatible Founder MVP reference.
# Existing Founder acceptance tests may still import this name.
FOUNDER_TOKENS = V1_ACTIVE_TOKENS


# ==========================================================
# Dashboard Results
# ==========================================================

def build_founder_dashboard_results(
    *,
    tokens: Iterable[str] | None = None,
    scan: Callable[[str], dict] = run_scan,
    venue_lookup: Callable[[str], list[dict[str, object]]] | None = None,
    technical_lookup: Callable[[str], dict[str, object]] | None = None,
    fundamental_context: dict[str, object] | None = None,
    market_catalysts: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    """
    Run sequential DexSato scans.

    When no explicit token collection is supplied, the
    approved V1 five-market universe is used.

    Invalid or failed tokens remain in the output as
    unavailable entries and do not stop subsequent scans.
    """

    resolved_tokens = (
        tokens
        if tokens is not None
        else V1_ACTIVE_TOKENS
    )

    results: list[dict[str, object]] = []

    for raw_token in resolved_tokens:

        display_token = str(
            raw_token,
        ).strip()

        try:

            normalized_token = normalize_token(
                display_token,
            )

            scan_result = scan(
                normalized_token,
            )

            card = extract_dashboard(
                scan_result,
            )

        except (
            RuntimeError,
            ValueError,
        ) as error:

            results.append(
                {
                    "token": (
                        display_token
                        or "UNKNOWN"
                    ),
                    "card": None,
                    "error": str(
                        error,
                    ),
                }
            )

            continue

        trading_venues: list[dict[str, object]] = []
        trading_venues_status = "NOT_REQUESTED"
        technical_evidence: dict[str, object] = {}
        technical_evidence_status = "NOT_REQUESTED"

        if venue_lookup is not None:
            try:
                trading_venues = venue_lookup(normalized_token)
                trading_venues_status = (
                    "AVAILABLE" if trading_venues else "NO_MATCH"
                )
            except Exception:
                # Venue discovery is optional presentation enrichment and
                # must never fail a market scan or affect its decision.
                trading_venues_status = "UNAVAILABLE"

        if technical_lookup is not None:
            try:
                technical_evidence = technical_lookup(normalized_token)
                technical_evidence_status = str(
                    technical_evidence.get("status", "UNAVAILABLE")
                ).upper()
            except Exception:
                # Technical evidence is read-only enrichment. Provider
                # failure must not alter or suppress the engine decision.
                technical_evidence_status = "UNAVAILABLE"

        results.append(
            {
                "token": normalized_token,
                "card": card,
                "market": scan_result.get(
                    "event",
                ),
                "trading_venues": trading_venues,
                "trading_venues_status": trading_venues_status,
                "technical_evidence": technical_evidence,
                "technical_evidence_status": technical_evidence_status,
                "fundamental_context": dict(fundamental_context or {}),
                "fundamental_context_status": str(
                    (fundamental_context or {}).get("status", "NOT_REQUESTED")
                ).upper(),
                "market_catalysts": dict(market_catalysts or {}),
                "market_catalysts_status": str(
                    (market_catalysts or {}).get("status", "NOT_REQUESTED")
                ).upper(),
                "error": None,
            }
        )

    return results
