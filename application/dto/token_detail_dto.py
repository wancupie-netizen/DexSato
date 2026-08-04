"""
DexSato Token Detail DTO

Public Data Transfer Objects used by the
Application Layer.

Responsibilities
----------------
- Represent API responses.
- Contain no business logic.
- Remain independent of Core Artifacts.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ==========================================================
# Header DTO
# ==========================================================

@dataclass(slots=True)
class TokenHeaderDTO:

    symbol: str

    pair: str

    chain: str

    price: str

    liquidity: str

    volume_24h: str

    market_cap: Optional[str] = None

    fdv: Optional[str] = None

    last_updated: Optional[str] = None


# ==========================================================
# Observation DTO
# ==========================================================

@dataclass(slots=True)
class ObservationDTO:

    data: dict


# ==========================================================
# Signal DTO
# ==========================================================

@dataclass(slots=True)
class SignalDTO:

    name: str


# ==========================================================
# Interpretation DTO
# ==========================================================

@dataclass(slots=True)
class InterpretationDTO:

    name: str

    description: str = ""


# ==========================================================
# Decision DTO
# ==========================================================

@dataclass(slots=True)
class DecisionDTO:

    recommended_action: str

    confidence: str

    summary: str

    artifact_id: str

    timestamp: str

    engine_version: str

    reasons: List[str] = field(default_factory=list)

    context: dict = field(default_factory=dict)


# ==========================================================
# Outcome DTO
# ==========================================================

@dataclass(slots=True)
class OutcomeDTO:

    snapshot_status: str

    observation_window: str

    artifact_id: str

    market_snapshot: dict


# ==========================================================
# Learning DTO
# ==========================================================

@dataclass(slots=True)
class LearningDTO:

    learning_status: str

    summary: str

    created_at: str

    artifact_id: str

    notes: Optional[str] = None


# ==========================================================
# Knowledge DTO
# ==========================================================

@dataclass(slots=True)
class KnowledgeDTO:

    token: str

    knowledge_fingerprint: str

    sample_size: int

    success_rate: float

    confidence: str

    summary: str

    artifact_id: str

    created_at: str


# ==========================================================
# Metadata DTO
# ==========================================================

@dataclass(slots=True)
class MetaDTO:

    version: str

    generated_at: str

    request_id: str

    processing_time_ms: int


# ==========================================================
# Token Detail DTO
# ==========================================================

@dataclass(slots=True)
class TokenDetailDTO:

    header: TokenHeaderDTO

    observation: ObservationDTO

    signals: List[SignalDTO]

    interpretations: List[InterpretationDTO]

    decision: Optional[DecisionDTO]

    outcome: Optional[OutcomeDTO]

    learning: Optional[LearningDTO]

    knowledge: List[KnowledgeDTO]

    meta: MetaDTO