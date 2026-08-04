"""
DexSato Explanation Engine

Convert machine intelligence into
human-readable explanations.
"""

from scanner.models import ExplanationResult


RECOMMENDATIONS = {

    "ALERT": "Immediate attention is recommended.",

    "WATCH": "Continue monitoring for confirmation.",

    "REVIEW": "Review recent market behaviour carefully.",

    "IGNORE": "No immediate action is required.",

}


def build_explanation(

    decision,

    interpretations,

    patterns,

):

    highlights = []

    for pattern in patterns:

        highlights.append(pattern.name)

    for interpretation in sorted(interpretations):

        highlights.append(interpretation)

    if patterns:

        summary = (

            f"{patterns[0].name} detected."

        )

    elif interpretations:

        summary = (

            f"{sorted(interpretations)[0]} detected."

        )

    else:

        summary = (

            "No significant market behaviour detected."

        )

    recommendation = RECOMMENDATIONS.get(

        decision["decision"],

        "Continue monitoring.",

    )

    return ExplanationResult(

        summary=summary,

        recommendation=recommendation,

        highlights=highlights,

    )