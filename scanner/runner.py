"""
DexSato Production Runner v1.0

Production Orchestrator

Responsibilities
----------------
- Coordinate complete scan lifecycle
- Orchestrate Intelligence Engine
- Orchestrate Lifecycle Engine
- Orchestrate Dashboard Engine
- Persist Intelligence
- Persist Lifecycle
- Return Production Result

Runner does NOT

- detect signals
- interpret markets
- make decisions
- serialize artifacts
- access business rules
"""

from __future__ import annotations

import traceback

from scanner.config import (
    DEFAULT_OBSERVATION_WINDOW,
)

# ==========================================================
# Infrastructure
# ==========================================================

from scanner.dexscreener import (
    fetch_registered_pair,
)

from scanner.market_registry import (
    get_market,
)

from scanner.normalizer import (
    normalize_pair,
)

from scanner.database import (
    save_market_event,
)

# ==========================================================
# Builders
# ==========================================================

from scanner.observation_builder import (
    build_observation,
)

from scanner.market_snapshot_builder import (
    build_market_snapshot,
)

# ==========================================================
# Intelligence
# ==========================================================

from scanner.intelligence_engine import (
    build_intelligence,
)

from scanner.knowledge_gate import (
    should_store,
)

from scanner.knowledge_fingerprint import (
    build_knowledge_fingerprint,
)

# ==========================================================
# Dashboard
# ==========================================================

from adaptive.dashboard.dashboard_request_builder import (
    build_dashboard_request,
)

from application.adaptive_dashboard_service import (
    build_adaptive_dashboard,
)

from application.adaptive_experience_service import (
    record_adaptive_experience,
)

# ==========================================================
# Lifecycle
# ==========================================================

from scanner.lifecycle_engine import (
    build_lifecycle,
)

# ==========================================================
# Serializers
# ==========================================================

from scanner.serializers.intelligence_serializer import (
    serialize_package,
)

from scanner.serializers.outcome_serializer import (
    serialize_outcome,
)

from scanner.serializers.learning_serializer import (
    serialize_learning,
)

from scanner.serializers.knowledge_serializer import (
    serialize_knowledge,
)

# ==========================================================
# Stores
# ==========================================================

from scanner.intelligence_store import (
    save_intelligence,
    load_latest_intelligence,
)

from scanner.outcome_store import (
    save_outcome,
)

from scanner.learning_store import (
    save_learning,
)

from scanner.knowledge_store import (
    save_knowledge,
)

# ==========================================================
# Pulse
# ==========================================================

from pulse.pulse import (
    start_job,
    finish_job,
)

# ==========================================================
# Constants
# ==========================================================

RUNNER_VERSION = "1.0.0"

# ==========================================================
# SECTION B
# Market Scan
# ==========================================================

def _scan_market(
    token: str,
) -> dict:
    """
    Execute the complete market scanning pipeline.

    Responsibilities
    ----------------
    - Scan DexScreener
    - Select best trading pair
    - Normalize market data
    - Persist market event
    - Build observation

    Returns
    -------
    dict

        event
        observation
        first_scan

    Raises
    ------
    ValueError

        No valid trading pair found.
    """

    # ------------------------------------------------------
    # Scan DexScreener
    # ------------------------------------------------------

    market = get_market(
        token,
    )

    # ------------------------------------------------------
    # Select Best Pair
    # ------------------------------------------------------

    selected_pair = fetch_registered_pair(market)

    # ------------------------------------------------------
    # Normalize
    # ------------------------------------------------------

    event = normalize_pair(
        selected_pair,
        token=market["token"],
        display_pair=market["display_pair"],
    )

    # ------------------------------------------------------
    # Persist Market Event
    # ------------------------------------------------------

    save_market_event(
        event,
    )

    # ------------------------------------------------------
    # Build Observation
    # ------------------------------------------------------

    observation = build_observation(
        token,
        pair_address=event["pair_address"],
    )

    # ------------------------------------------------------
    # First Scan Detection
    # ------------------------------------------------------

    if observation is None:

        return {

            "event":
                event,

            "observation":
                None,

            "first_scan":
                True,

        }

    # ------------------------------------------------------
    # Normal Flow
    # ------------------------------------------------------

    return {

        "event":
            event,

        "observation":
            observation,

        "first_scan":
            False,

    }

# ==========================================================
# SECTION C
# Intelligence Builder
# ==========================================================

def _build_intelligence(
    token: str,
    observation: dict,
) ->dict:
    """
    Build the complete Intelligence Package.

    Responsibilities
    ----------------
    - Build Intelligence Package
    - Evaluate Knowledge Gate
    - Load latest Intelligence Package

    Returns
    -------
    dict

        intelligence_package
        latest_package
        should_persist
    """

    # ------------------------------------------------------
    # Intelligence Engine
    # ------------------------------------------------------

    intelligence_package = build_intelligence(

        token=
            token,

        observation=
            observation,

    )

    # ------------------------------------------------------
    # Load Latest Intelligence
    # ------------------------------------------------------

    latest_package = load_latest_intelligence(
        token,
    )

    # ------------------------------------------------------
    # Knowledge Gate
    # ------------------------------------------------------

    should_persist = should_store(

        intelligence_package,

        latest_package,

    )

    return {

        "intelligence_package":
            intelligence_package,

        "latest_package":
            latest_package,

        "should_persist":
            should_persist,

    }

# ==========================================================
# SECTION D
# Lifecycle Builder
# ==========================================================

def _build_lifecycle(
    *,
    decision,
    event: dict,
) -> dict:
    """
    Build the complete Lifecycle Package.

    Responsibilities
    ----------------
    - Build MarketSnapshot
    - Execute Lifecycle Engine

    Returns
    -------
    dict

        lifecycle_package
    """

    # ------------------------------------------------------
    # Market Snapshot
    # ------------------------------------------------------

    market_snapshot = build_market_snapshot(
        event,
    )

    # ------------------------------------------------------
    # Lifecycle Engine
    # ------------------------------------------------------

    lifecycle_package = build_lifecycle(

        decision=
            decision,

        market_snapshot=
            market_snapshot,

        observation_window=
            DEFAULT_OBSERVATION_WINDOW,

    )

    return {

        "market_snapshot":
            market_snapshot,

        "lifecycle_package":
            lifecycle_package,

    }

# ==========================================================
# SECTION E
# Intelligence Persistence
# ==========================================================

def _persist_intelligence(
    intelligence_package: dict,
    knowledge_fingerprint: str,
) -> bool:
    """
    Persist Intelligence Package.

    Responsibilities
    ----------------
    - Serialize Intelligence Package
    - Persist Intelligence

    Parameters
    ----------
    intelligence_package
        Complete Intelligence Package.

    knowledge_fingerprint
        Precomputed Knowledge Fingerprint.

    Returns
    -------
    bool
    """

    # ------------------------------------------------------
    # Serialize
    # ------------------------------------------------------

    serialized_package = serialize_package(

        intelligence_package,

    )

    # ------------------------------------------------------
    # Payload
    # ------------------------------------------------------

    payload = {

        "token":
            serialized_package[
                "token"
            ],

        "decision":
            serialized_package[
                "decision"
            ][
                "recommended_action"
            ],

        "confidence":
            serialized_package[
                "decision"
            ][
                "confidence"
            ],

        "knowledge_fingerprint":
            knowledge_fingerprint,

        "intelligence_package":
            serialized_package,

    }

    # ------------------------------------------------------
    # Persist
    # ------------------------------------------------------

    save_intelligence(

        payload,

    )

    return True

# ==========================================================
# SECTION F
# Lifecycle Persistence
# ==========================================================

def _persist_lifecycle(
    lifecycle_package: dict,
) -> bool:
    """
    Persist the complete Lifecycle Package.

    Responsibilities
    ----------------
    - Persist Outcome
    - Persist Learning
    - Persist Knowledge

    Returns
    -------
    bool
    """

    # ------------------------------------------------------
    # Extract Artifacts
    # ------------------------------------------------------

    outcome = lifecycle_package[
        "outcome"
    ]

    learning = lifecycle_package[
        "learning"
    ]

    knowledge = lifecycle_package[
        "knowledge"
    ]

    # ------------------------------------------------------
    # Outcome
    # ------------------------------------------------------

    outcome_payload = serialize_outcome(
        outcome,
    )

    save_outcome(
        outcome_payload,
    )

    # ------------------------------------------------------
    # Learning
    # ------------------------------------------------------

    learning_payload = serialize_learning(
        learning,
    )

    save_learning(
        learning_payload,
    )

    # ------------------------------------------------------
    # Knowledge
    # ------------------------------------------------------

    knowledge_payload = serialize_knowledge(
        knowledge,
    )

    save_knowledge(
        knowledge_payload,
    )

    return True

# ==========================================================
# SECTION G
# Finish Helpers
# ==========================================================

def _finish_success(
    *,
    job,
    token: str,
    event: dict,
    intelligence_package: dict,
    lifecycle_package: dict,
    dashboard,
    knowledge_persisted: bool,
) -> dict:
    """
    Finish a successful scan.
    """

    duration = finish_job(

        job,

        "SUCCESS",

    )

    return {

        "success":
            True,

        "job_status":
            "SUCCESS",

        "token":
            token,

        "duration_ms":
            duration,

        # --------------------------------------------------
        # Infrastructure
        # --------------------------------------------------

        "event":
            event,

        # --------------------------------------------------
        # Intelligence
        # --------------------------------------------------

        "intelligence_package":
            intelligence_package,

        "knowledge_saved":
            knowledge_persisted,

        # --------------------------------------------------
        # Dashboard
        # --------------------------------------------------

        "dashboard":
            dashboard,

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        "lifecycle_package":
            lifecycle_package,

        # --------------------------------------------------
        # Backward Compatibility
        # --------------------------------------------------

        "observation":
            intelligence_package[
                "observation"
            ],

        "signals":
            intelligence_package[
                "signals"
            ],

        "interpretations":
            intelligence_package[
                "interpretations"
            ],

        "decision":
            intelligence_package[
                "decision"
            ],

    }


def _finish_failure(
    *,
    job,
    token: str,
    error: Exception,
) -> dict:
    """
    Finish a failed scan.
    """

    print(
        "\n❌ DexSato Exception"
    )

    traceback.print_exc()

    try:

        finish_job(

            job,

            "FAILED",

            str(error),

        )

    except Exception:

        print(
            "\n⚠️ Pulse Update Failed"
        )

        traceback.print_exc()

    return {

        "success":
            False,

        "job_status":
            "FAILED",

        "token":
            token,

        "error":
            str(error),

    }

# ==========================================================
# SECTION H
# Production Runner
# ==========================================================

def run_scan(
    token: str,
) -> dict:
    """
    Run a complete DexSato Production Scan.

    Flow
    ----
    Market
        ↓
    Intelligence
        ↓
    Knowledge Fingerprint
        ↓
    Intelligence Persistence
        ↓
    Adaptive Dashboard
        ↓
    Lifecycle
        ↓
    Lifecycle Persistence
        ↓
    Adaptive Experience
        ↓
    Production Result
    """

    job = start_job(
        token,
    )

    try:

        # --------------------------------------------------
        # Market
        # --------------------------------------------------

        market = _scan_market(
            token,
        )

        # --------------------------------------------------
        # First Scan
        # --------------------------------------------------

        if market.get(
            "first_scan",
            False,
        ):

            duration = finish_job(
                job,
                "SUCCESS",
            )

            return {

                "success":
                    True,

                "job_status":
                    "SUCCESS",

                "token":
                    token,

                "duration_ms":
                    duration,

                "event":
                    market["event"],

                "message":
                    (
                        "First market event recorded. "
                        "Waiting for next scan."
                    ),

            }

        event = market[
            "event"
        ]

        observation = market[
            "observation"
        ]

        # --------------------------------------------------
        # Intelligence
        # --------------------------------------------------

        intelligence = _build_intelligence(

            token=
                token,

            observation=
                observation,

        )

        intelligence_package = intelligence[
            "intelligence_package"
        ]

        should_persist = intelligence[
            "should_persist"
        ]

        decision = intelligence_package[
            "decision"
        ]

        # --------------------------------------------------
        # Knowledge Fingerprint
        # --------------------------------------------------

        knowledge_fingerprint = build_knowledge_fingerprint(
            intelligence_package,
        )

        # --------------------------------------------------
        # Intelligence Persistence
        # --------------------------------------------------

        knowledge_saved = False

        if should_persist:

            _persist_intelligence(

                intelligence_package,
                knowledge_fingerprint,

            )

            knowledge_saved = True

        # --------------------------------------------------
        # Adaptive Dashboard
        # --------------------------------------------------

        dashboard_request = build_dashboard_request(

            token=
                token,

            decision=
                decision,

            knowledge_fingerprint=
                knowledge_fingerprint,

            last_updated=
                decision.metadata.timestamp,

        )

        dashboard = build_adaptive_dashboard(
            dashboard_request,
        )

        # --------------------------------------------------
        # Lifecycle
        # --------------------------------------------------

        lifecycle = _build_lifecycle(

            decision=
                decision,

            event=
                event,

        )

        lifecycle_package = lifecycle[
            "lifecycle_package"
        ]

        # --------------------------------------------------
        # Lifecycle Persistence
        # --------------------------------------------------

        _persist_lifecycle(
            lifecycle_package,
        )

        # --------------------------------------------------
        # Adaptive Experience
        # --------------------------------------------------

        learning = lifecycle_package[
            "learning"
        ]

        record_adaptive_experience(

            knowledge_fingerprint=
                knowledge_fingerprint,

            learning=
                learning,

        )

        # --------------------------------------------------
        # Finish
        # --------------------------------------------------

        return _finish_success(

            job=
                job,

            token=
                token,

            event=
                event,

            intelligence_package=
                intelligence_package,

            lifecycle_package=
                lifecycle_package,

            dashboard=
                dashboard,

            knowledge_persisted=
                knowledge_saved,

        )

    except Exception as error:

        return _finish_failure(

            job=
                job,

            token=
                token,

            error=
                error,

        )
