"""
DexSato Decision Engine

Convert market interpretations into an official DecisionArtifact.

Responsibilities
----------------
- Evaluate market interpretations
- Produce a recommendation
- Preserve reasoning

This module does NOT:
- perform validation
- execute trades
- predict prices
- perform learning
"""

from datetime import datetime, timezone

from scanner.decision_types import (
    DecisionType,
    DECISION_PRIORITY,
    DECISION_CONFIDENCE,
)

from scanner.interpretation_types import InterpretationType

from core.artifacts.decision_artifact import (
    DecisionArtifact,
    DecisionContext,
    DecisionMetadata,
    Reason,
)

# --------------------------------------------------
# Decision Rules
# --------------------------------------------------

DECISION_RULES = {

    # Strong Opportunities
    InterpretationType.STRONG_MOMENTUM:
        DecisionType.ALERT,

    InterpretationType.EARLY_MOMENTUM:
        DecisionType.WATCH,

    InterpretationType.ACCUMULATION:
        DecisionType.WATCH,

    # Review Required
    InterpretationType.DISTRIBUTION:
        DecisionType.REVIEW,

    InterpretationType.WEAK_BREAKOUT:
        DecisionType.REVIEW,

    InterpretationType.RISKY_ACTIVITY:
        DecisionType.REVIEW,

    InterpretationType.THIN_BREAKOUT:
        DecisionType.REVIEW,

    InterpretationType.WEAK_MOMENTUM:
        DecisionType.REVIEW,

    # Ignore
    InterpretationType.LOW_ACTIVITY:
        DecisionType.IGNORE,

    InterpretationType.LOW_INTEREST:
        DecisionType.IGNORE,
}


# --------------------------------------------------
# Decision Engine
# --------------------------------------------------

def make_decision(
    interpretations: set[InterpretationType],
    *,
    symbol: str,
    pair: str,
    engine_version: str = "1.0.0",
) -> DecisionArtifact:
    """
    Produce an immutable DecisionArtifact from market interpretations.

    Validation is intentionally NOT performed here.
    Decision Gate is responsible for validation.
    """

    candidate_decisions: set[DecisionType] = set()

    for interpretation in interpretations:

        decision = DECISION_RULES.get(interpretation)

        if decision is not None:
            candidate_decisions.add(decision)

    if candidate_decisions:

        final_decision = max(
            candidate_decisions,
            key=lambda decision: DECISION_PRIORITY[decision]
        )

    else:

        final_decision = DecisionType.IGNORE

    reasons = tuple(
        Reason(
            title=reason.value,
            description="Derived from Interpretation Engine",
        )
        for reason in sorted(
            interpretations,
            key=lambda item: item.value
        )
    )

    context = DecisionContext()

    metadata = DecisionMetadata(
        engine_version=engine_version,
        timestamp=datetime.now(timezone.utc),
        symbol=symbol,
        pair=pair,
        interpretation_version="1.0.0",
    )

    return DecisionArtifact(
        recommended_action=final_decision.value,
        confidence=DECISION_CONFIDENCE[final_decision],
        summary=f"Recommended action: {final_decision.value}",
        context=context,
        reasons=reasons,
        metadata=metadata,
    )