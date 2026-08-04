"""
DexSato Intelligence Deserializer

Deserialize Intelligence Packages.

Responsibilities
----------------
- Convert JSON-safe Intelligence Packages into
  application-ready structures.
- Delegate Decision deserialization.
- Contain no business logic.
- Contain no persistence logic.

This module does NOT:
- load data
- save data
- validate intelligence
"""

from scanner.deserializers.decision_deserializer import (
    deserialize_decision,
)


def deserialize_package(
    payload: dict,
) -> dict:
    """
    Deserialize an Intelligence Package.
    """

    return {

        "token":
            payload["token"],

        "observation":
            payload["observation"],

        "signals":
            list(
                payload.get(
                    "signals",
                    [],
                )
            ),

        "interpretations":
            list(
                payload.get(
                    "interpretations",
                    [],
                )
            ),

        "decision":
            deserialize_decision(
                payload["decision"]
            ),

    }