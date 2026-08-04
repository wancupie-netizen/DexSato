"""
DexSato Intelligence Serializer

Serialize Intelligence Packages into JSON-safe structures.

Responsibilities
----------------
- Serialize Intelligence Packages
- Delegate Decision serialization
- Contain no persistence logic
- Contain no business logic

This module does NOT:
- save data
- load data
- deserialize artifacts
"""

from scanner.serializers.decision_serializer import (
    serialize_decision,
)

from core.artifacts.decision_artifact import (
    DecisionArtifact,
)


def serialize_package(
    package: dict,
) -> dict:
    """
    Serialize an Intelligence Package into a JSON-safe dict.
    """

    decision = package["decision"]

    if isinstance(
        decision,
        DecisionArtifact,
    ):

        decision = serialize_decision(
            decision,
        )

    return {

        "token":
            package["token"],

        "observation":
            package["observation"],

        "signals":

            sorted(

                signal.value
                if hasattr(signal, "value")
                else signal

                for signal in package["signals"]

            ),

        "interpretations":

            sorted(

                interpretation.value
                if hasattr(
                    interpretation,
                    "value",
                )
                else interpretation

                for interpretation
                in package["interpretations"]

            ),

        "decision":
            decision,

    }