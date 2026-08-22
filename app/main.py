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
- Expose the founder-only Content Control Center

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
    Request,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)
from fastapi.staticfiles import StaticFiles

from application.content_control_service import (
    COOKIE_NAME,
    ai_enabled as content_ai_enabled,
    ai_model as content_ai_model,
    build_content_facts,
    content_control_configured,
    create_session_token,
    find_market,
    generate_x_draft,
    password_matches,
    session_is_valid,
)
from application.founder_snapshot_service import (
    read_latest_snapshot,
)

from application.telegram_notifier import (
    send_telegram_alert,
)
from application.system_health_dashboard import (
    collect_system_dashboard_status,
)

from presentation.content_control_presenter import (
    render_content_control,
    render_content_login,
)
from presentation.dexsato_dashboard_presenter import (
    render_market_detail_page,
)
from presentation.dexsato_admin_presenter import (
    render_admin_system_page,
)
from presentation.dexsato_user_dashboard_presenter import (
    render_user_dashboard,
)

render_founder_snapshot_dashboard = render_user_dashboard


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


def _content_session_valid(request: Request) -> bool:
    return session_is_valid(request.cookies.get(COOKIE_NAME))


def _content_cookie_secure(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded.lower() == "https"


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
    "/admin/system",
    response_class=HTMLResponse,
)
def admin_system() -> str:
    """Display the internal operations console without running a scan."""
    try:
        snapshot = load_current_snapshot()
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return render_admin_system_page(
        snapshot,
        system_status=collect_system_dashboard_status(),
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


@app.get("/api/markets/{token}/chart")
def market_chart_api(token: str, timeframe: str = "4h") -> dict[str, object]:
    """Return registered-token chart candles without running a scan."""
    from application.market_chart_service import (
        MarketChartUnavailable,
        fetch_market_chart,
    )

    try:
        return fetch_market_chart(token, timeframe)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except MarketChartUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Live market chart is temporarily unavailable.",
        ) from error

@app.get(
    "/content-control",
    response_class=HTMLResponse,
)
def content_control(request: Request) -> str:
    """Display the private founder Content Control Center."""
    if not _content_session_valid(request):
        return render_content_login(configured=content_control_configured())

    try:
        snapshot = load_current_snapshot()
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return render_content_control(
        snapshot,
        ai_enabled=content_ai_enabled(),
        ai_model=content_ai_model(),
    )


@app.post("/content-control/login")
async def content_control_login(request: Request) -> JSONResponse:
    """Create a signed founder session after password verification."""
    if not content_control_configured():
        raise HTTPException(
            status_code=503,
            detail="Content Control Center authentication is not configured.",
        )
    try:
        payload = await request.json()
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid login request.") from error
    if not isinstance(payload, dict) or not password_matches(payload.get("password")):
        raise HTTPException(status_code=401, detail="Invalid founder password.")

    response = JSONResponse({"status": "ok"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(),
        max_age=60 * 60 * 12,
        httponly=True,
        secure=_content_cookie_secure(request),
        samesite="strict",
        path="/content-control",
    )
    return response


@app.post("/content-control/logout")
def content_control_logout() -> JSONResponse:
    """Clear the founder Content Control Center session."""
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(key=COOKIE_NAME, path="/content-control")
    return response


@app.post("/content-control/generate")
async def content_control_generate(request: Request) -> dict[str, object]:
    """Generate one editable X draft from existing DexSato snapshot facts."""
    if not _content_session_valid(request):
        raise HTTPException(status_code=401, detail="Founder authentication required.")

    try:
        payload = await request.json()
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid generation request.") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid generation request.")

    try:
        snapshot = load_current_snapshot()
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    coin = find_market(snapshot, payload.get("token"))
    if coin is None:
        raise HTTPException(status_code=404, detail="Market is not available.")

    facts = build_content_facts(coin)
    try:
        result = generate_x_draft(
            facts,
            content_type=str(payload.get("content_type") or "current_update"),
            style=str(payload.get("style") or "trader"),
            length=str(payload.get("length") or "medium"),
        )
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"AI writing request failed: {error}",
        ) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    return result


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
