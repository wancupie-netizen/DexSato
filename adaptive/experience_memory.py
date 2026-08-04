from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Experience:
    """
    Immutable record of a single DexSato decision experience.
    """

    decision_id: str
    decision_fingerprint: str
    market_dna: str
    decision: str
    confidence: float
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class ExperienceMemory:
    """
    Append-only in-memory experience store.

    Future implementations may replace this storage with
    SQLite, Supabase, DuckDB or Vector DB without changing
    the public API.
    """

    def __init__(self) -> None:

        self._experiences: list[Experience] = []

        self._by_decision_id: dict[str, Experience] = {}

        self._by_market_dna: dict[str, list[Experience]] = {}

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def add(self, experience: Experience) -> None:
        """
        Append a new experience.

        Decision IDs must be globally unique.
        """

        if experience.decision_id in self._by_decision_id:
            raise ValueError(
                f"Duplicate decision_id: {experience.decision_id}"
            )

        self._experiences.append(experience)

        self._by_decision_id[
            experience.decision_id
        ] = experience

        self._by_market_dna.setdefault(
            experience.market_dna,
            []
        ).append(experience)

    def all(self) -> list[Experience]:
        """
        Return all experiences.
        """

        return list(self._experiences)

    def count(self) -> int:
        """
        Total number of experiences.
        """

        return len(self._experiences)

    def find_by_decision_id(
        self,
        decision_id: str
    ) -> Experience | None:

        return self._by_decision_id.get(
            decision_id
        )

    def find_by_market_dna(
        self,
        market_dna: str
    ) -> list[Experience]:

        return list(
            self._by_market_dna.get(
                market_dna,
                []
            )
        )

    def exists(
        self,
        decision_id: str
    ) -> bool:

        return decision_id in self._by_decision_id

    def clear(self) -> None:
        """
        Testing helper.
        """

        self._experiences.clear()
        self._by_decision_id.clear()
        self._by_market_dna.clear()