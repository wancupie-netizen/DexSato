"""
DexSato Fingerprint Builder

Build decision fingerprint from
Intelligence Package.

Responsibilities
----------------
- Adapt Intelligence Package
- Generate Decision Fingerprint

This module does NOT:
- perform hashing
- access repositories
- access databases
"""

from adaptive.identity.decision_fingerprint import (
    generate_decision_fingerprint,
)


# --------------------------------------------------
# Fingerprint Builder
# --------------------------------------------------

def build_fingerprint(
    intelligence_package: dict,
) -> str:
    """
    Build fingerprint from
    Intelligence Package.
    """

    observation = intelligence_package[
        "observation"
    ]

    observations = observation.get(

        "observation_types",

        [],

    )

    return generate_decision_fingerprint(

        decision=intelligence_package[
            "decision"
        ],

        observations=observations,

        signals=intelligence_package[
            "signals"
        ],

        interpretations=intelligence_package[
            "interpretations"
        ],

    )