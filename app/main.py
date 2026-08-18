"""
DexSato V1 FastAPI Application.

Official launcher:

    python main.py

Dashboard:

    http://127.0.0.1:8000

Responsibilities
----------------
- Read the latest stored Top 100 snapshot
- Display the snapshot dashboard
- Expose snapshot JSON
- Send snapshot data to Telegram
- Expose application health

This module does NOT:
- run scans when pages are opened
- schedule scans
- calculate market decisions
"""

from __future__ import annotations

from pathlib import Path

import requests

from fastapi import (
    FastAPI,
    HTTPException,
)
from fastapi.responses import (
    HTMLResponse,
)
from fastapi.staticfiles import StaticFiles

from application.founder_snapshot_service import (
    read_latest_snapshot,
)

from application.telegram_notifier import (
    send_telegram_alert,
)
from application.system_health_dashboard import (
    collect_system_dashboard_status,
)

from presentation.dexsato_dashboard_presenter import (
    render_dexsato_dashboard,
    render_market_detail_page,
)

render_founder_snapshot_dashboard = render_dexsato_dashboard


APP_TITLE = "DexSato V1"

APP_VERSION = "1.0.0"

HOST = "127.0.0.1"

PORT = 8000


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
)

app.mount(
    "/static",
    StaticFiles(
        directory=Path(__file__).resolve().parents[1] / "static",
    ),
    name="static",
)


def load_current_snapshot() -> dict[str, object]:
    """
    Read the latest generated DexSato snapshot.
    """

    return read_latest_snapshot()


def build_current_dashboard_data() -> list[dict[str, object]]:
    """
    Return serialized coin data from the latest snapshot.
    """

    snapshot = load_current_snapshot()

    coins = snapshot.get(
        "coins",
    )

    if not isinstance(
        coins,
        list,
    ):

        raise RuntimeError(
            "Latest DexSato snapshot coin data is invalid."
        )

    return coins


@app.get(
    "/",
    response_class=HTMLResponse,
)
def founder_home() -> str:
    """
    Display the latest Top 100 snapshot.
    """

    try:

        snapshot = load_current_snapshot()

    except (
        FileNotFoundError,
        RuntimeError,
    ) as error:

        raise HTTPException(
            status_code=503,
            detail=str(
                error,
            ),
        ) from error

    system_status = collect_system_dashboard_status()

    return render_founder_snapshot_dashboard(
        snapshot,
        system_status=system_status,
    )


@app.get(
    "/market/{token}",
    response_class=HTMLResponse,
)
def market_detail(token: str) -> str:
    """Display one market workspace from the latest stored snapshot."""
    try:
        snapshot = load_current_snapshot()
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    coins = snapshot.get("coins")
    if not isinstance(coins, list):
        raise HTTPException(status_code=503, detail="Snapshot coin data is invalid.")

    normalized = str(token).strip().upper()
    coin = next(
        (
            item
            for item in coins
            if isinstance(item, dict)
            and str(item.get("token", "")).strip().upper() == normalized
        ),
        None,
    )
    if coin is None:
        raise HTTPException(status_code=404, detail="Market is not available.")

    return render_market_detail_page(
        coin,
        generated_at=snapshot.get("generated_at"),
    )


@app.get(
    "/api/dashboard",
)
def dashboard_api() -> dict[str, object]:
    """
    Return the complete latest snapshot.
    """

    try:

        return load_current_snapshot()

    except (
        FileNotFoundError,
        RuntimeError,
    ) as error:

        raise HTTPException(
            status_code=503,
            detail=str(
                error,
            ),
        ) from error


@app.get(
    "/api/system-status",
)
def system_status_api() -> dict[str, object]:
    """
    Return operational health without running a market scan.
    """

    return collect_system_dashboard_status()


@app.post(
    "/telegram/send",
)
def telegram_send() -> dict[str, object]:
    """
    Send the latest stored snapshot to Telegram.

    Digest filtering will be added in V1-04.
    """

    try:

        dashboard_data = (
            build_current_dashboard_data()
        )

        return send_telegram_alert(
            dashboard_data=dashboard_data,
        )

    except (
        FileNotFoundError,
        RuntimeError,
    ) as error:

        raise HTTPException(
            status_code=503,
            detail=str(
                error,
            ),
        ) from error

    except requests.RequestException as error:

        raise HTTPException(
            status_code=502,
            detail=(
                "Telegram API request failed: "
                f"{error}"
            ),
        ) from error


@app.get(
    "/health",
)
def health_check() -> dict[str, str]:
    """
    Return application readiness.
    """

    return {
        "status": "ok",
        "application": APP_TITLE,
        "version": APP_VERSION,
    }


def run() -> None:
    """
    Start the DexSato V1 server.
    """

    import uvicorn

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
    )


if __name__ == "__main__":

    run()
