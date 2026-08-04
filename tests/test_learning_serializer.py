"""
Tests for DexSato Learning Serializer.
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

from core.models.market_snapshot import (
    MarketSnapshot,
)

from scanner.serializers.learning_serializer import (
    serialize_learning,
)


print("=" * 60)
print("Learning Serializer Test")
print("=" * 60)

decision = DecisionArtifact(

    recommended_action="WATCH",

    confidence="HIGH",

    summary="Learning Serializer Test",

    context=DecisionContext(),

    reasons=(),

    metadata=DecisionMetadata(

        engine_version="1.0.0",

        symbol="BTC",

        pair="BTC/USDT",

    ),

)

snapshot = MarketSnapshot(

    symbol="BTC",

    pair="BTC/USDT",

    chain="solana",

    price=Decimal("80000"),

    liquidity=Decimal("5000000"),

    volume_24h=Decimal("1200000"),

)

outcome = OutcomeArtifact.from_decision(

    decision=decision,

    market_snapshot=snapshot,

    observation_window="24H",

)

learning = LearningArtifact.from_outcome(

    outcome=outcome,

    learning_status="PENDING",

    summary="Initial learning",

)

payload = serialize_learning(
    learning,
)

print("\nPayload")
print("-" * 60)
pprint(payload)

assert payload["token"] == "BTC"

assert payload["outcome_artifact_id"] == outcome.artifact_id

assert payload["learning_artifact_id"] == learning.artifact_id

assert payload["learning_status"] == "PENDING"

assert payload["summary"] == "Initial learning"

assert payload["metadata"]["engine_version"] == "1.0.0"

assert payload["created_at"] == learning.created_at.isoformat()

print("\nPASS")