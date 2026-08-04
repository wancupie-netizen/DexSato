"""
DexSato Live Dashboard Verification.

Verifies that a DashboardCard returned by the Production Runner
matches the Intelligence and Adaptive history used to build it.

Responsibilities
----------------
- Run or inspect a Production Runner result
- Verify direct DecisionArtifact-to-DashboardCard mapping
- Verify Knowledge Fingerprint
- Verify Adaptive history values
- Produce a readable verification report

This module does NOT:
- modify production artifacts
- persist data
- generate HTML
- make trading decisions
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from adaptive.dashboard.dashboard_card import (
    DashboardCard,
)

from adaptive.history.history_builder import (
    build_history_summary,
)

from adaptive.history.history_repository import (
    find,
)

from scanner.knowledge_fingerprint import (
    build_knowledge_fingerprint,
)

from scanner.runner import (
    run_scan,
)


# ==========================================================
# Verification Result
# ==========================================================

@dataclass(frozen=True)
class DashboardVerificationResult:
    """
    Result of live Dashboard data verification.
    """

    token_matches: bool

    decision_matches: bool

    confidence_matches: bool

    summary_matches: bool

    reasons_match: bool

    timestamp_matches: bool

    historical_success_matches: bool

    seen_before_matches: bool

    knowledge_fingerprint: str

    history_sample_size: int

    expected_historical_success: float

    actual_historical_success: float

    all_checks_passed: bool


# ==========================================================
# Result Extraction
# ==========================================================

def extract_live_artifacts(
    result: dict,
) -> tuple[dict, DashboardCard]:
    """
    Extract Intelligence Package and DashboardCard
    from a successful Production Runner result.
    """

    if not result.get(
        "success",
        False,
    ):

        raise RuntimeError(
            str(
                result.get(
                    "error",
                    "DexSato scan failed.",
                )
            )
        )

    intelligence_package = result.get(
        "intelligence_package",
    )

    dashboard = result.get(
        "dashboard",
    )

    if intelligence_package is None:

        raise RuntimeError(
            "Runner result contains no Intelligence Package."
        )

    if not isinstance(
        dashboard,
        DashboardCard,
    ):

        raise RuntimeError(
            "Runner result contains no valid DashboardCard."
        )

    return (
        intelligence_package,
        dashboard,
    )


# ==========================================================
# Verification
# ==========================================================

def verify_dashboard_result(
    result: dict,
) -> DashboardVerificationResult:
    """
    Verify a Production Runner Dashboard against its sources.
    """

    intelligence_package, dashboard = extract_live_artifacts(
        result,
    )

    decision = intelligence_package[
        "decision"
    ]

    fingerprint = build_knowledge_fingerprint(
        intelligence_package,
    )

    experiences = find(
        fingerprint,
    )

    history = build_history_summary(
        experiences,
    )

    expected_reasons = [
        reason.title
        for reason in decision.reasons
    ]

    token_matches = (
        dashboard.token
        == result["token"]
    )

    decision_matches = (
        dashboard.decision
        == decision.recommended_action
    )

    confidence_matches = (
        dashboard.confidence
        == decision.confidence
    )

    summary_matches = (
        dashboard.summary
        == decision.summary
    )

    reasons_match = (
        dashboard.reasons
        == expected_reasons
    )

    timestamp_matches = (
        dashboard.last_updated
        == decision.metadata.timestamp
    )

    historical_success_matches = (
        dashboard.historical_success
        == history.success_rate
    )

    seen_before_matches = (
        dashboard.seen_before
        == history.seen_before
    )

    checks = [

        token_matches,

        decision_matches,

        confidence_matches,

        summary_matches,

        reasons_match,

        timestamp_matches,

        historical_success_matches,

        seen_before_matches,

    ]

    return DashboardVerificationResult(

        token_matches=
            token_matches,

        decision_matches=
            decision_matches,

        confidence_matches=
            confidence_matches,

        summary_matches=
            summary_matches,

        reasons_match=
            reasons_match,

        timestamp_matches=
            timestamp_matches,

        historical_success_matches=
            historical_success_matches,

        seen_before_matches=
            seen_before_matches,

        knowledge_fingerprint=
            fingerprint,

        history_sample_size=
            history.sample_size,

        expected_historical_success=
            history.success_rate,

        actual_historical_success=
            dashboard.historical_success,

        all_checks_passed=
            all(checks),

    )


# ==========================================================
# Report
# ==========================================================

def render_verification_report(
    verification: DashboardVerificationResult,
) -> str:
    """
    Render a readable console verification report.
    """

    def status(
        passed: bool,
    ) -> str:

        return (
            "PASS"
            if passed
            else "FAIL"
        )

    return "\n".join(
        [
            "=" * 60,
            "DexSato Live Dashboard Verification",
            "=" * 60,
            "",
            (
                "Token Mapping             : "
                f"{status(verification.token_matches)}"
            ),
            (
                "Decision Mapping          : "
                f"{status(verification.decision_matches)}"
            ),
            (
                "Confidence Mapping        : "
                f"{status(verification.confidence_matches)}"
            ),
            (
                "Summary Mapping           : "
                f"{status(verification.summary_matches)}"
            ),
            (
                "Reasons Mapping           : "
                f"{status(verification.reasons_match)}"
            ),
            (
                "Timestamp Mapping         : "
                f"{status(verification.timestamp_matches)}"
            ),
            (
                "Historical Success        : "
                f"{status(verification.historical_success_matches)}"
            ),
            (
                "Seen-Before Status        : "
                f"{status(verification.seen_before_matches)}"
            ),
            "",
            (
                "Knowledge Fingerprint     : "
                f"{verification.knowledge_fingerprint}"
            ),
            (
                "History Sample Size       : "
                f"{verification.history_sample_size}"
            ),
            (
                "Expected History Success  : "
                f"{verification.expected_historical_success:.2f}%"
            ),
            (
                "Dashboard History Success : "
                f"{verification.actual_historical_success:.2f}%"
            ),
            "",
            (
                "FINAL RESULT              : "
                f"{status(verification.all_checks_passed)}"
            ),
            "=" * 60,
        ]
    )


# ==========================================================
# CLI
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(

        description=(
            "Verify DexSato live Dashboard data provenance."
        ),

    )

    parser.add_argument(

        "token",

        help="Token symbol, for example BTC.",

    )

    return parser.parse_args()


def main() -> int:
    """
    Run a live scan and verify Dashboard provenance.
    """

    arguments = parse_arguments()

    token = arguments.token.strip().upper()

    result = run_scan(
        token,
    )

    try:

        verification = verify_dashboard_result(
            result,
        )

    except RuntimeError as error:

        print()

        print(
            f"Verification unavailable: {error}"
        )

        print()

        return 1

    print()

    print(
        render_verification_report(
            verification,
        )
    )

    print()

    return (
        0
        if verification.all_checks_passed
        else 1
    )


if __name__ == "__main__":

    raise SystemExit(
        main()
    )