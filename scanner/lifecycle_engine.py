"""
DexSato Lifecycle Engine

Coordinate the complete lifecycle from
DecisionArtifact to KnowledgeArtifact.

Responsibilities
----------------
- Validate DecisionArtifact
- Build OutcomeArtifact
- Build LearningArtifact
- Build KnowledgeArtifact
- Return Lifecycle Package

Lifecycle Engine does NOT:
- access databases
- serialize objects
- persist artifacts
- access external APIs
"""

from scanner.decision_gate import validate

from scanner.outcome_engine import (
    record_outcome,
)

from scanner.learning_engine import (
    build_learning,
)

from core.knowledge.aggregator import (
    build_knowledge,
)

from core.models.market_snapshot import (
    MarketSnapshot,
)


ENGINE_VERSION = "1.0.0"


def build_lifecycle(
    *,
    decision,
    market_snapshot: MarketSnapshot,
    observation_window: str,
) -> dict:
    """
    Build the complete lifecycle package.

    Parameters
    ----------
    decision
        DecisionArtifact.

    market_snapshot
        MarketSnapshot collected after the
        observation window.

    observation_window
        Example:
            15m
            1h
            4h
            1d

    Returns
    -------
    dict
    """

    # ------------------------------------------------------
    # Decision Gate
    # ------------------------------------------------------

    gate = validate(
        decision,
    )

    if gate.status != "APPROVED":

        raise ValueError(
            "DecisionArtifact rejected by Decision Gate."
        )

    # ------------------------------------------------------
    # Outcome
    # ------------------------------------------------------

    outcome = record_outcome(

        gate_result=gate,

        market_snapshot=market_snapshot,

        observation_window=observation_window,

    )

    # ------------------------------------------------------
    # Learning
    # ------------------------------------------------------

    learning = build_learning(
        outcome,
    )

    # ------------------------------------------------------
    # Knowledge
    # ------------------------------------------------------

    knowledge = build_knowledge(
        [learning],
    )

    # ------------------------------------------------------
    # Lifecycle Package
    # ------------------------------------------------------

    return {

        "decision":
            decision,

        "gate":
            gate,

        "outcome":
            outcome,

        "learning":
            learning,

        "knowledge":
            knowledge,

    }