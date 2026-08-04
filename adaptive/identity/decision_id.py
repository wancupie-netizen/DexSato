"""
DexSato Adaptive Intelligence
Decision ID Generator

Responsibilities
----------------
Generate a unique identifier for every Decision Snapshot.

Notes
-----
- Stateless
- Thread-safe
- Zero external dependencies
- Pure function
"""

from uuid import uuid4


def generate_decision_id() ->str:
    """
    Generate a unique Decision ID.

    Returns
    -------
    str
        UUID4 string.
    """

    return str(uuid4())