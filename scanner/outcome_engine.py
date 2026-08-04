"""
DexSato Outcome Engine

Record the observed market outcome after
a DecisionArtifact has passed the Decision Gate.

Responsibilities
----------------
- Accept approved GateResult
- Record market reality
- Produce OutcomeArtifact

Outcome Engine does NOT

- generate decisions
- modify DecisionArtifact
- perform learning
- evaluate trading performance
"""

from scanner.core.gate_result import GateResult

from core.artifacts.outcome_artifact import OutcomeArtifact
from core.models.market_snapshot import MarketSnapshot


ENGINE_VERSION = "1.0.0"


def record_outcome(
    gate_result: GateResult,
    market_snapshot: MarketSnapshot,
    observation_window: str,
) -> OutcomeArtifact:
    """
    Record market outcome.

    Parameters
    ----------
    gate_result
        Approved GateResult.

    market_snapshot
        Snapshot collected after the
        observation window.

    observation_window
        Example:
            15m
            1h
            4h
            1d

    Returns
    -------
    OutcomeArtifact
    """

    if gate_result.status != "APPROVED":

        raise ValueError(
            "Outcome Engine accepts only APPROVED GateResult."
        )

    return OutcomeArtifact.from_decision(

        decision=gate_result.artifact,

        market_snapshot=market_snapshot,

        observation_window=observation_window,

        snapshot_status="RECORDED",

    )