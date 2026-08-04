"""
Tests for DexSato Knowledge Serializer.
"""

from decimal import Decimal
from pprint import pprint

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

from scanner.serializers.knowledge_serializer import (
    serialize_knowledge,
)


print("=" * 60)
print("Knowledge Serializer Test")
print("=" * 60)


# ==========================================================
# Decision
# ==========================================================

decision = DecisionArtifact(

    recommended_action="WATCH",

    confidence="HIGH",

    summary="Knowledge Serializer Test",

    context=DecisionContext(),

    reasons=(),

    metadata=DecisionMetadata(

        engine_version="1.0.0",

        symbol="BTC",

        pair="BTC/USDT",

    ),

)


# ==========================================================
# Snapshot
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


# ==========================================================
# Serialize
# ==========================================================

payload = serialize_knowledge(
    knowledge,
)

print("\nPayload")
print("-" * 60)
pprint(payload)


# ==========================================================
# Assertions
# ==========================================================

assert payload["token"] == "BTC"

assert payload["learning_artifact_id"] == learning.artifact_id

assert payload["knowledge_artifact_id"] == knowledge.artifact_id

assert payload["knowledge_fingerprint"] == "WATCH|ACCUMULATION"

assert payload["sample_size"] == 10

assert payload["success_rate"] == 82.5

assert payload["confidence"] == "HIGH"

assert payload["summary"] == "Historical pattern is reliable."

assert payload["metadata"]["engine_version"] == "1.0.0"

assert payload["created_at"] == knowledge.created_at.isoformat()

print("\nPASS")