"""
AlphaRadar Environment Configuration.

Loads local Founder V1 configuration from the project-level
.env file.

Supported values
----------------
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
PUBLIC_DASHBOARD_URL
SCAN_TIME_1
SCAN_TIME_2
SCAN_TIME_3

Configuration policy
--------------------
- Existing operating-system environment variables take priority.
- The project .env file supplies missing values.
- The .env file is never committed to Git.
- Scheduler times use local Windows time in HH:MM format.

This module does NOT:
- create the .env file
- store credentials in Git
- register Windows scheduled tasks
- send Telegram messages
- run market scans
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


# ==========================================================
# Paths and Defaults
# ==========================================================

PROJECT_ROOT = Path(
    __file__,
).resolve().parent.parent


DEFAULT_ENV_FILE = (
    PROJECT_ROOT
    / ".env"
)


DEFAULT_SCAN_TIMES = (
    "08:00",
    "14:00",
    "20:00",
)


SCAN_TIME_VARIABLES = (
    "SCAN_TIME_1",
    "SCAN_TIME_2",
    "SCAN_TIME_3",
)


# ==========================================================
# Environment Loading
# ==========================================================

def load_environment(
    *,
    env_file: Path = DEFAULT_ENV_FILE,
    override: bool = False,
) -> dict[str, object]:
    """
    Load the AlphaRadar project environment.

    Operating-system values remain authoritative unless
    override=True is explicitly supplied.
    """

    resolved_file = Path(
        env_file,
    ).resolve()

    env_file_exists = (
        resolved_file.exists()
    )

    loaded = False

    if env_file_exists:

        loaded = load_dotenv(
            dotenv_path=resolved_file,
            override=override,
        )

    return {
        "success": True,
        "env_file": str(
            resolved_file,
        ),
        "env_file_exists": env_file_exists,
        "loaded": bool(
            loaded,
        ),
    }


# ==========================================================
# Scan Time Configuration
# ==========================================================

def normalize_scan_time(
    value: object,
) -> str:
    """
    Validate and normalize one local scan time.

    Accepted format:

        HH:MM
    """

    candidate = str(
        value,
    ).strip()

    try:

        parsed = datetime.strptime(
            candidate,
            "%H:%M",
        )

    except ValueError as error:

        raise ValueError(
            "Scan time must use 24-hour HH:MM format: "
            f"{candidate or 'EMPTY'}."
        ) from error

    return parsed.strftime(
        "%H:%M",
    )


def get_scan_times(
    *,
    environment: Mapping[
        str,
        str,
    ] | None = None,
    defaults: tuple[
        str,
        ...,
    ] = DEFAULT_SCAN_TIMES,
) -> tuple[str, ...]:
    """
    Resolve the three Founder V1 scan times.

    Missing values fall back to:

        08:00
        14:00
        20:00
    """

    source = (
        environment
        if environment is not None
        else os.environ
    )

    resolved: list[str] = []

    for index, variable_name in enumerate(
        SCAN_TIME_VARIABLES,
    ):

        fallback = defaults[
            index
        ]

        configured = source.get(
            variable_name,
            fallback,
        )

        resolved.append(
            normalize_scan_time(
                configured,
            )
        )

    if len(
        set(
            resolved,
        )
    ) != len(
        resolved,
    ):

        raise ValueError(
            "AlphaRadar scan times must be unique."
        )

    return tuple(
        resolved,
    )


# ==========================================================
# Configuration Status
# ==========================================================

def get_configuration_status(
    *,
    environment: Mapping[
        str,
        str,
    ] | None = None,
    env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, object]:
    """
    Return a credential-safe configuration summary.

    Secret values are never returned.
    """

    source = (
        environment
        if environment is not None
        else os.environ
    )

    token_configured = bool(
        str(
            source.get(
                "TELEGRAM_BOT_TOKEN",
                "",
            )
        ).strip()
    )

    chat_id_configured = bool(
        str(
            source.get(
                "TELEGRAM_CHAT_ID",
                "",
            )
        ).strip()
    )

    public_dashboard_url_configured = bool(
        str(
            source.get(
                "PUBLIC_DASHBOARD_URL",
                "",
            )
        ).strip()
    )

    scan_times = get_scan_times(
        environment=source,
    )

    resolved_env_file = Path(
        env_file,
    ).resolve()

    return {
        "success": True,
        "env_file": str(
            resolved_env_file,
        ),
        "env_file_exists": (
            resolved_env_file.exists()
        ),
        "telegram_bot_token_configured": (
            token_configured
        ),
        "telegram_chat_id_configured": (
            chat_id_configured
        ),
        "public_dashboard_url_configured": (
            public_dashboard_url_configured
        ),
        "scan_times": scan_times,
        "ready": (
            token_configured
            and chat_id_configured
        ),
    }