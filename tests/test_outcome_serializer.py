"""
Tests for DexSato Outcome Serializer.
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

from core.models.market_snapshot import (
    MarketSnapshot,
)

from scanner.serializers.outcome_serializer import (
    serialize_outcome,
)


print("=" * 60)
print("Outcome Serializer Test")
print("=" * 60)

decision = DecisionArtifact(

    recommended_action="WATCH",

    confidence="HIGH",

    summary="Serializer Test",

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

payload = serialize_outcome(
    outcome,
)

print("\nPayload")
print("-" * 60)
pprint(payload)

assert payload["token"] == "BTC"

assert payload["decision_artifact_id"] == decision.artifact_id

assert payload["outcome_artifact_id"] == outcome.artifact_id

assert payload["snapshot_status"] == "RECORDED"

assert payload["observation_window"] == "24H"

assert payload["market_snapshot"]["symbol"] == "BTC"

assert payload["created_at"] == outcome.created_at.isoformat()

print("\nPASS")