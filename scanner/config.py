"""
DexSato Scanner Configuration

Centralized runtime configuration for
Production Runner.
"""

from core.enums.observation_window import (
    ObservationWindow,
)

DEFAULT_OBSERVATION_WINDOW = (
    ObservationWindow.HOURS_24
)