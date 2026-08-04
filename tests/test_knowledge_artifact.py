"""
Tests for DexSato Knowledge Artifact.
"""

from decimal import Decimal

from core.artifacts.decision_artifact import (
    DecisionArtifact,
    DecisionContext,
    DecisionMetadata,
)

from core.artifacts.outcome_artifact import (
    OutcomeArtifact,
)

from core.artifacts.learning_artifact import (
    LearningArtifact,
)

from core.artifacts.knowledge_artifact import (
    KnowledgeArtifact,
)

from core.models.market_snapshot import (
    MarketSnapshot,
)


print("=" * 60)
print("Knowledge Artifact Test")
print("=" * 60)


# ==========================================================
# Decision
# ==========================================================

decision = DecisionArtifact(

    recommended_action="WATCH",

    confidence="HIGH",

    summary="Knowledge Test",

    context=DecisionContext(),

    reasons=(),

    metadata=DecisionMetadata(

        engine_version="1.0.0",

        symbol="BTC",

        pair="BTC/USDT",

    ),

)


# ==========================================================
# Market Snapshot
# ==========================================================

snapshot = MarketSnapshot(

    symbol="BTC",

    pair="BTC/USDT",

    chain="solana",

    price=Decimal("80000"),

    liquidity=Decimal("5000000"),

    volume_24h=Decimal("1200000"),

)


# ==========================================================
# Outcome
# ==========================================================

outcome = OutcomeArtifact.from_decision(

    decision=decision,

    market_snapshot=snapshot,

    observation_window="24H",

)


# ==========================================================
# Learning
# ==========================================================

learning = LearningArtifact.from_outcome(

    outcome=outcome,

    learning_status="PENDING",

    summary="Initial learning",

)


# ==========================================================
# Knowledge
# ==========================================================

knowledge = KnowledgeArtifact.from_learning(

    learning=learning,

    knowledge_fingerprint="WATCH|ACCUMULATION",

    sample_size=10,

    success_rate=82.5,

    confidence="HIGH",

    summary="Historical pattern is reliable.",

)


print(knowledge)


# ==========================================================
# Assertions
# ==========================================================

assert knowledge.token == "BTC"

assert knowledge.learning_artifact_id == learning.artifact_id

assert knowledge.knowledge_fingerprint == "WATCH|ACCUMULATION"

assert knowledge.sample_size == 10

assert knowledge.success_rate == 82.5

assert knowledge.confidence == "HIGH"

assert knowledge.summary == "Historical pattern is reliable."

assert knowledge.created_at is not None

assert knowledge.metadata.engine_version == "1.0.0"


print("\nPASS")