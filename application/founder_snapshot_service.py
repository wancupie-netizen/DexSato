"""
DexSato Founder Snapshot Service.

Builds and stores the latest serialized Top 100 market
snapshot.

Responsibilities
----------------
- Run the Founder Dashboard service once
- Serialize scan results
- Save one JSON snapshot atomically
- Read the latest snapshot
- Preserve snapshot generation time

This module does NOT:
- schedule scans
- render HTML
- send Telegram messages
- start FastAPI
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from application.founder_dashboard_data import (
    serialize_founder_dashboard_results,
)

from application.founder_dashboard_service import (
    build_founder_dashboard_results,
)

from application.commodity_dashboard_service import (
    build_commodity_reference_results,
)
from application.trading_venue_service import (
    fetch_trading_venues,
)
from application.technical_evidence_service import (
    fetch_technical_evidence,
)
from application.fundamental_context_service import fetch_fundamental_context
from application.market_catalyst_service import fetch_market_catalysts


LATEST_SNAPSHOT_FILE = Path(
    "output",
    "snapshots",
    "latest_snapshot.json",
)


def build_complete_dashboard_results(
    *, fundamental_lookup: Callable[[], dict[str, object]] = fetch_fundamental_context,
    catalyst_lookup: Callable[[], dict[str, object]] = fetch_market_catalysts,
) -> list[dict[str, object]]:
    """Build crypto decisions plus commodity reference markets."""
    try:
        fundamental_context = fundamental_lookup()
    except Exception:
        # Official macro context is optional, read-only enrichment.
        fundamental_context = {"status": "UNAVAILABLE"}
    try:
        market_catalysts = catalyst_lookup()
    except Exception:
        market_catalysts = {"status": "UNAVAILABLE"}
    return [
        *build_founder_dashboard_results(
            venue_lookup=fetch_trading_venues,
            technical_lookup=fetch_technical_evidence,
            fundamental_context=fundamental_context,
            market_catalysts=market_catalysts,
        ),
        *build_commodity_reference_results(),
    ]


def build_snapshot_payload(
    *,
    results: list[dict[str, object]],
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """
    Build one JSON-safe snapshot payload.
    """

    resolved_generated_at = (
        generated_at
        or datetime.now(
            timezone.utc,
        )
    )

    if resolved_generated_at.tzinfo is None:

        raise ValueError(
            "Snapshot timestamp must be timezone-aware."
        )

    coins = serialize_founder_dashboard_results(
        results,
    )

    available_count = sum(
        1
        for coin in coins
        if coin["available"] is True
    )

    return {
        "generated_at": (
            resolved_generated_at.isoformat()
        ),
        "total_coins": len(
            coins,
        ),
        "available_coins": available_count,
        "unavailable_coins": (
            len(coins)
            - available_count
        ),
        "coins": coins,
    }


def write_latest_snapshot(
    *,
    payload: dict[str, object],
    snapshot_file: Path = LATEST_SNAPSHOT_FILE,
) -> Path:
    """
    Write the latest snapshot atomically.

    A temporary file is written first and then replaces the
    previous snapshot, preventing partial JSON reads.
    """

    if not isinstance(
        payload,
        dict,
    ):

        raise ValueError(
            "Snapshot payload must be a dictionary."
        )

    snapshot_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = snapshot_file.with_suffix(
        ".tmp",
    )

    temporary_file.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        snapshot_file,
    )

    return snapshot_file.resolve()


def read_latest_snapshot(
    *,
    snapshot_file: Path = LATEST_SNAPSHOT_FILE,
) -> dict[str, Any]:
    """
    Read and validate the latest stored snapshot.
    """

    if not snapshot_file.exists():

        raise FileNotFoundError(
            "Latest DexSato snapshot is not available."
        )

    try:

        payload = json.loads(
            snapshot_file.read_text(
                encoding="utf-8",
            )
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            "Latest DexSato snapshot contains invalid JSON."
        ) from error

    if not isinstance(
        payload,
        dict,
    ):

        raise RuntimeError(
            "Latest DexSato snapshot is invalid."
        )

    required_fields = {
        "generated_at",
        "total_coins",
        "available_coins",
        "unavailable_coins",
        "coins",
    }

    if not required_fields.issubset(
        payload,
    ):

        raise RuntimeError(
            "Latest DexSato snapshot is incomplete."
        )

    if not isinstance(
        payload["coins"],
        list,
    ):

        raise RuntimeError(
            "Latest DexSato snapshot coin data is invalid."
        )

    return payload


def generate_latest_snapshot(
    *,
    snapshot_file: Path = LATEST_SNAPSHOT_FILE,
    build_results: Callable[
        [],
        list[dict[str, object]],
    ] = build_complete_dashboard_results,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """
    Run one full scan and replace the latest snapshot.
    """

    results = build_results()

    payload = build_snapshot_payload(
        results=results,
        generated_at=generated_at,
    )

    output_file = write_latest_snapshot(
        payload=payload,
        snapshot_file=snapshot_file,
    )

    return {
        "success": True,
        "snapshot_file": str(
            output_file,
        ),
        "generated_at": payload[
            "generated_at"
        ],
        "total_coins": payload[
            "total_coins"
        ],
        "available_coins": payload[
            "available_coins"
        ],
        "unavailable_coins": payload[
            "unavailable_coins"
        ],
    }
