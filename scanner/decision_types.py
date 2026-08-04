"""
DexSato Decision Types

Decision Types represent the final recommendation produced by the
Decision Engine.

A Decision is NOT:
- a trading execution
- a price prediction
- financial advice

It is an intelligence recommendation based on the current market state.
"""

from enum import StrEnum


class DecisionType(StrEnum):
    IGNORE = "IGNORE"
    REVIEW = "REVIEW"
    WATCH = "WATCH"
    ALERT = "ALERT"


# --------------------------------------------------
# Decision Priority
#
# Higher number = Higher priority
# --------------------------------------------------

DECISION_PRIORITY = {
    DecisionType.IGNORE: 1,
    DecisionType.REVIEW: 2,
    DecisionType.WATCH: 3,
    DecisionType.ALERT: 4,
}


# --------------------------------------------------
# Default Confidence
#
# Initial confidence mapping.
# This may become dynamic in future versions.
# --------------------------------------------------

DECISION_CONFIDENCE = {
    DecisionType.IGNORE: "LOW",
    DecisionType.REVIEW: "MEDIUM",
    DecisionType.WATCH: "MEDIUM",
    DecisionType.ALERT: "HIGH",
}