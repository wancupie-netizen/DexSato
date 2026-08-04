"""
DexSato Outcome Deserializer

Deserialize stored Outcome payloads into
official OutcomeArtifact objects.

Responsibilities
----------------
- Reconstruct MarketSnapshot
- Reconstruct OutcomeArtifact

This module does NOT:
- perform market analysis
- perform learning
- build DTOs
- access database
"""

from datetime import datetime
from decimal import Decimal

from core.artifacts.outcome_artifact import (
    OutcomeArtifact,
)

from core.models.market_snapshot import (
    MarketSnapshot,
)


# --------------------------------------------------
# Deserialize
# --------------------------------------------------

def deserialize_outcome(
    payload: dict,
) -> OutcomeArtifact:
    """
    Deserialize an Outcome payload.

    Parameters
    ----------
    payload : dict

    Returns
    -------
    OutcomeArtifact
    """

    snapshot_data = payload["market_snapshot"]

    snapshot = MarketSnapshot(

        symbol=
            snapshot_data["symbol"],

        pair=
            snapshot_data["pair"],

        chain=
            snapshot_data["chain"],

        price=
            Decimal(
                str(snapshot_data["price"])
            ),

        liquidity=
            Decimal(
                str(snapshot_data["liquidity"])
            ),

        volume_24h=
            Decimal(
                str(snapshot_data["volume_24h"])
            ),

        market_cap=(

            Decimal(
                str(snapshot_data["market_cap"])
            )

            if snapshot_data["market_cap"] is not None

            else None

        ),

        fdv=(

            Decimal(
                str(snapshot_data["fdv"])
            )

            if snapshot_data["fdv"] is not None

            else None

        ),

        captured_at=
            datetime.fromisoformat(
                snapshot_data["captured_at"]
            ),

    )

    return OutcomeArtifact(

        decision_artifact_id=
            payload["decision_artifact_id"],

        observation_window=
            payload["observation_window"],

        market_snapshot=
            snapshot,

        snapshot_status=
            payload["snapshot_status"],

        artifact_id=
            payload["outcome_artifact_id"],

    )