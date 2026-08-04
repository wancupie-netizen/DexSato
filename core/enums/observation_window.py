"""
DexSato Observation Window

Official observation windows supported by
the Lifecycle Engine.

Responsibilities
----------------
- Provide a single source of truth for
  observation windows.
- Eliminate hardcoded string literals.
- Improve type safety.

This module contains no business logic.
"""

from enum import StrEnum


class ObservationWindow(StrEnum):
    """
    Official observation windows used
    throughout DexSato.
    """

    MINUTES_15 = "15M"

    HOUR_1 = "1H"

    HOURS_4 = "4H"

    HOURS_24 = "24H"