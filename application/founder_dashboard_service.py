"""
DexSato Founder Dashboard Service.

Runs the existing DexSato engine sequentially for the
approved V1 active market universe.

V1 Active Markets
-----------------
- BTC
- ETH
- BNB
- XRP
- SOL
- DOGE
- ADA
- SUI
- LINK
- AVAX

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
    "BNB",
    "XRP",
    "SOL",
    "DOGE",
    "ADA",
    "SUI",
    "LINK",
    "AVAX",
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
) -> list[dict[str, object]]:
    """
    Run sequential DexSato scans.

    When no explicit token collection is supplied, the
    approved V1 ten-coin universe is used.

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

        results.append(
            {
                "token": normalized_token,
                "card": card,
                "error": None,
            }
        )

    return results