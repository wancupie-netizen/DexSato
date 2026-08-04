"""
DexSato Token Mapper

Translate Core Artifacts into Token Detail DTOs.

Responsibilities
----------------
- Convert Core Artifacts into API DTOs.
- Contain no business logic.
- Contain no market analysis.
- Contain no persistence logic.
"""

from datetime import datetime
from uuid import uuid4

from application.dto.token_detail_dto import (
    DecisionDTO,
    InterpretationDTO,
    KnowledgeDTO,
    LearningDTO,
    MetaDTO,
    ObservationDTO,
    OutcomeDTO,
    SignalDTO,
    TokenDetailDTO,
    TokenHeaderDTO,
)

from core.artifacts.decision_artifact import DecisionArtifact
from core.artifacts.outcome_artifact import OutcomeArtifact
from core.artifacts.learning_artifact import LearningArtifact
from core.artifacts.knowledge_artifact import KnowledgeArtifact


def _iso(value) -> str:

    if value is None:
        return ""

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def build_token_detail(

    *,

    header: dict,

    observation: dict,

    signals: list,

    interpretations: list,

    decision: DecisionArtifact | None,

    outcome: OutcomeArtifact | None,

    learning: LearningArtifact | None,

    knowledge: list[KnowledgeArtifact],

) -> TokenDetailDTO:

    header_dto = TokenHeaderDTO(

        symbol=header.get("symbol", ""),

        pair=header.get("pair", ""),

        chain=header.get("chain", ""),

        price=str(header.get("price", "")),

        liquidity=str(header.get("liquidity", "")),

        volume_24h=str(header.get("volume_24h", "")),

        market_cap=str(header.get("market_cap", "")),

        fdv=str(header.get("fdv", "")),

        last_updated=_iso(
            header.get("last_updated")
        ),
    )

    observation_dto = ObservationDTO(

        data=observation,
    )

    signal_dto = [

        SignalDTO(
            name=str(signal)
        )

        for signal in signals

    ]

    interpretation_dto = [

        InterpretationDTO(
            name=str(item)
        )

        for item in interpretations

    ]

    # --------------------------------------------------
    # Decision
    # --------------------------------------------------

    decision_dto = None

    if decision is not None:

        decision_dto = DecisionDTO(

            recommended_action=decision.recommended_action,

            confidence=str(decision.confidence),

            summary=decision.summary,

            artifact_id=decision.artifact_id,

            timestamp=_iso(
                decision.metadata.timestamp
            ),

            engine_version=decision.metadata.engine_version,

            reasons=[
                reason.title
                for reason in decision.reasons
            ],

            context={

                "trend": decision.context.trend,

                "market_bias": decision.context.market_bias,

                "risk": decision.context.risk,

            },

        )

    # --------------------------------------------------
    # Outcome
    # --------------------------------------------------

    outcome_dto = None

    if outcome is not None:

        snapshot = outcome.market_snapshot

        outcome_dto = OutcomeDTO(

            snapshot_status=outcome.snapshot_status,

            observation_window=outcome.observation_window,

            artifact_id=outcome.artifact_id,

            market_snapshot={

                "symbol": snapshot.symbol,

                "pair": snapshot.pair,

                "chain": snapshot.chain,

                "price": str(snapshot.price),

                "liquidity": str(snapshot.liquidity),

                "volume_24h": str(snapshot.volume_24h),

                "market_cap": (
                    str(snapshot.market_cap)
                    if snapshot.market_cap is not None
                    else None
                ),

                "fdv": (
                    str(snapshot.fdv)
                    if snapshot.fdv is not None
                    else None
                ),

                "captured_at": _iso(
                    snapshot.captured_at
                ),

            },

        )

    # --------------------------------------------------
    # Learning
    # --------------------------------------------------

    learning_dto = None

    if learning is not None:

        learning_dto = LearningDTO(

            learning_status=learning.learning_status,

            summary=learning.summary,

            created_at=_iso(
                learning.created_at
            ),

            artifact_id=learning.artifact_id,

            notes=learning.notes,

        )

    # --------------------------------------------------
    # Knowledge
    # --------------------------------------------------

    knowledge_dto = [

        KnowledgeDTO(

            token=item.token,

            knowledge_fingerprint=item.knowledge_fingerprint,

            sample_size=item.sample_size,

            success_rate=item.success_rate,

            confidence=item.confidence,

            summary=item.summary,

            artifact_id=item.artifact_id,

            created_at=_iso(
                item.created_at
            ),

        )

        for item in knowledge

    ]

    meta = MetaDTO(

        version="v1",

        generated_at=_iso(
            datetime.utcnow()
        ),

        request_id=str(uuid4()),

        processing_time_ms=0,

    )

    return TokenDetailDTO(

        header=header_dto,

        observation=observation_dto,

        signals=signal_dto,

        interpretations=interpretation_dto,

        decision=decision_dto,

        outcome=outcome_dto,

        learning=learning_dto,

        knowledge=knowledge_dto,

        meta=meta,

    )