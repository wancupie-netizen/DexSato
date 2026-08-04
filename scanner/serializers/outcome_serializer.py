"""
DexSato Outcome Serializer

Serialize OutcomeArtifact into a database payload.

Responsibilities
----------------
- Convert OutcomeArtifact into dict.
- Produce payload compatible with outcome_events.
- Contain no business logic.

This module does NOT:
- access databases
- deserialize objects
- evaluate outcomes
"""

from core.artifacts.outcome_artifact import (
    OutcomeArtifact,
)


# ==========================================================
# Serializer
# ==========================================================

def serialize_outcome(
    artifact: OutcomeArtifact,
) -> dict:
    """
    Serialize an OutcomeArtifact.

    Parameters
    ----------
    artifact : OutcomeArtifact

    Returns
    -------
    dict
    """

    snapshot = artifact.market_snapshot

    return {

        "token":
            snapshot.symbol,

        "decision_artifact_id":
            artifact.decision_artifact_id,

        "outcome_artifact_id":
            artifact.artifact_id,

        "snapshot_status":
            artifact.snapshot_status,

        "observation_window":
            artifact.observation_window,

        "market_snapshot": {

            "snapshot_id":
                snapshot.snapshot_id,

            "symbol":
                snapshot.symbol,

            "pair":
                snapshot.pair,

            "chain":
                snapshot.chain,

            "price":
                str(snapshot.price),

            "liquidity":
                str(snapshot.liquidity),

            "volume_24h":
                str(snapshot.volume_24h),

            "market_cap":
                (
                    str(snapshot.market_cap)
                    if snapshot.market_cap is not None
                    else None
                ),

            "fdv":
                (
                    str(snapshot.fdv)
                    if snapshot.fdv is not None
                    else None
                ),

            "buyers_24h":
                snapshot.buyers_24h,

            "sellers_24h":
                snapshot.sellers_24h,

            "transactions_24h":
                snapshot.transactions_24h,

            "provider":
                snapshot.provider,

            "captured_at":
                snapshot.captured_at.isoformat(),

        },

        "created_at":
            artifact.created_at.isoformat(),

    }