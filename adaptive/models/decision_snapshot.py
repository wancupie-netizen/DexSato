"""
DexSato Decision Snapshot

Immutable snapshot captured immediately after a market decision.

Responsibilities
----------------
- Represent the cognitive state at the moment of decision
- Preserve decision context
- Provide a stable contract for Adaptive Intelligence

This model is NOT:
- a database model
- an API response
- a storage schema
- an ORM entity
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from scanner.decision_types import DecisionType


@dataclass(frozen=True, slots=True)
class DecisionSnapshot:
    """
    Immutable Decision Snapshot.

    A Decision Snapshot represents the complete cognitive state
    of DexSato immediately after the Decision Engine
    produces its recommendation.
    """

    # --------------------------------------------------
    # Identity
    # --------------------------------------------------

    decision_id: str

    decision_fingerprint: str

    market_dna: str

    # --------------------------------------------------
    # Decision
    # --------------------------------------------------

    token: str

    decision: DecisionType

    confidence: str

    reasons: list[str]

    # --------------------------------------------------
    # Cognitive Context
    # --------------------------------------------------

    observations: list[str]

    signals: list[str]

    interpretations: list[str]

    market_snapshot: dict

    # --------------------------------------------------
    # Metadata
    # --------------------------------------------------

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    engine_version: str = "0.6.1"

    pipeline_version: str = "6.1"

    contract_version: str = "1.0"