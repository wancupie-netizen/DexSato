"""
DexSato Domain Models

Domain models shared across the Intelligence Engine.

Responsibilities
----------------
- Define immutable domain objects
- Provide a common language across modules

This module does NOT:
- access databases
- call APIs
- contain business logic
"""

from dataclasses import dataclass, field
from typing import Any


# ==================================================
# Knowledge Summary
# ==================================================

@dataclass(slots=True, frozen=True)
class KnowledgeSummary:
    """
    Statistical summary of historical knowledge.
    """

    total_events: int

    latest_decision: str | None

    latest_confidence: str | None

    decision_frequency: dict[str, int]

    most_common_decision: str | None


# ==================================================
# Knowledge Context
# ==================================================

@dataclass(slots=True, frozen=True)
class KnowledgeContext:
    """
    Historical context used to enrich intelligence.
    """

    history: list[dict]

    summary: KnowledgeSummary

    patterns: list[str] = field(default_factory=list)

    trend: str | None = None


# ==================================================
# Pattern Result
# ==================================================

@dataclass(slots=True, frozen=True)
class PatternResult:
    """
    A detected historical market pattern.
    """

    name: str

    confidence: float

    description: str


# ==================================================
# Decision Result
# ==================================================

@dataclass(slots=True, frozen=True)
class DecisionResult:
    """
    Final decision produced by the Decision Engine.
    """

    decision: str

    confidence: str

    reasons: list[str]


# ==================================================
# Explanation Result
# ==================================================

@dataclass(slots=True, frozen=True)
class ExplanationResult:
    """
    Human-readable explanation generated
    from DexSato intelligence.
    """

    summary: str

    recommendation: str

    highlights: list[str]


# ==================================================
# Intelligence Package
# ==================================================

@dataclass(slots=True, frozen=True)
class IntelligencePackage:
    """
    Canonical Intelligence Package produced by DexSato.
    """

    token: str

    observation: dict[str, Any]

    signals: list[str]

    interpretations: list[str]

    decision: dict[str, Any]

    context: KnowledgeContext

    explanation: ExplanationResult