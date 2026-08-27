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
    Depends,
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

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
from application.solana_discovery_feed_service import (
    load_solana_discovery_feed,
)
from application.solana_discovery_token_service import (
    load_solana_discovery_live_candles,
    load_solana_discovery_token,
    load_solana_discovery_transactions,
)

from application.telegram_notifier import (
    send_telegram_alert,
)
from application.system_health_dashboard import (
    collect_system_dashboard_status,
)
from application.production_security import (
    ApplicationBoundaryMiddleware,
    SecurityHeadersMiddleware,
    allowed_hosts,
    application_host,
    application_port,
    require_internal_access,
    safe_jupiter_error_detail,
    trusted_proxy_headers,
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
from presentation.dexsato_solana_discovery_presenter import (
    render_solana_discovery_page,
)
from presentation.dexsato_solana_discovery_token_presenter import (
    render_solana_discovery_token_page,
)

render_founder_snapshot_dashboard = render_user_dashboard


APP_TITLE = "DexSato V1"

APP_VERSION = "1.0.0"

HOST = application_host()

PORT = application_port()


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(ApplicationBoundaryMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())

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
    if request.url.scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "")
    return trusted_proxy_headers() and forwarded.lower() == "https"


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
            detail="Market snapshot is temporarily unavailable.",
        ) from error

    system_status = collect_system_dashboard_status()

    return render_founder_snapshot_dashboard(
        snapshot,
        system_status=system_status,
    )


@app.get(
    "/discovery/solana",
    response_class=HTMLResponse,
)
def solana_discovery(view: str = "qualified", page: int = 1, q: str = "") -> str:
    """Display the read-only Solana Discovery D1 prototype."""
    return render_solana_discovery_page(
        load_solana_discovery_feed(view=view, page=page, page_size=25, query=q)
    )


@app.get(
    "/discovery/solana/{token_address}",
    response_class=HTMLResponse,
)
def solana_discovery_token(token_address: str) -> str:
    """Display one qualified exact-token workspace and its controlled swap pilot."""
    detail = load_solana_discovery_token(token_address)
    if detail is None:
        raise HTTPException(status_code=404, detail="Qualified discovery token is not available.")
    feed = load_solana_discovery_feed()
    return render_solana_discovery_token_page(detail, feed=feed)


# CHART_V22_LIVE_CANDLE
@app.get("/api/discovery/solana/{token_address}/candles")
def solana_discovery_live_candles(
    token_address: str,
    timeframe: str = "5m",
) -> dict[str, object]:
    try:
        payload = load_solana_discovery_live_candles(token_address, timeframe)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Live candle data is temporarily unavailable.",
        ) from error

    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Qualified discovery token is not available.",
        )
    return payload


# TRANSACTIONS_FEED_V11_API_ROUTE
@app.get("/api/discovery/solana/{token_address}/transactions")
def solana_discovery_transactions(token_address: str) -> dict[str, object]:
    """Return verified recent exact-pool transactions for one qualified token."""
    try:
        payload = load_solana_discovery_transactions(token_address)
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Live transaction data is temporarily unavailable.",
        ) from error

    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Qualified discovery token is not available.",
        )
    return payload


@app.get("/api/discovery/solana/{token_address}/jupiter-quote")
def solana_discovery_jupiter_quote(
    token_address: str,
    amount_sol: str = "0.1",
) -> dict[str, object]:
    """Return a quote-only Jupiter order for one qualified discovery token."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
        fetch_jupiter_quote,
    )

    try:
        return fetch_jupiter_quote(token_address, amount_sol)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter quote sandbox is not configured.",
        ) from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter quote is temporarily unavailable.",
        ) from error


async def _jupiter_swap_body(request: Request, permitted: set[str]) -> dict[str, object]:
    """Accept only the public wallet and transaction fields required by D6."""
    try:
        payload = await request.json()
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="A valid JSON request body is required.") from error
    if not isinstance(payload, dict) or set(payload) - permitted:
        raise HTTPException(status_code=400, detail="Unsupported swap request fields were rejected.")
    return payload


@app.post("/api/discovery/solana/{token_address}/jupiter-order")
async def solana_discovery_jupiter_order(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Prepare an unsigned transaction after an explicit mainnet risk acknowledgement."""
    from application.jupiter_quote_service import JupiterQuoteNotConfigured, JupiterQuoteUnavailable
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapRejected,
        prepare_jupiter_swap,
    )

    payload = await _jupiter_swap_body(
        request,
        {"amount_sol", "wallet_address", "risk_acknowledged"},
    )
    try:
        return prepare_jupiter_swap(
            token_address,
            payload.get("amount_sol"),
            str(payload.get("wallet_address") or ""),
            risk_acknowledged=payload.get("risk_acknowledged") is True,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(status_code=503, detail="Jupiter swap pilot is not configured.") from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(status_code=503, detail=safe_jupiter_error_detail(error)) from error


@app.post("/api/discovery/solana/{token_address}/jupiter-execute")
async def solana_discovery_jupiter_execute(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Relay a transaction already approved and signed by the connected wallet."""
    from application.jupiter_quote_service import JupiterQuoteNotConfigured, JupiterQuoteUnavailable
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapRejected,
        execute_jupiter_swap,
    )

    payload = await _jupiter_swap_body(
        request,
        {"request_id", "wallet_address", "signed_transaction"},
    )
    try:
        return execute_jupiter_swap(
            token_address,
            str(payload.get("request_id") or ""),
            str(payload.get("wallet_address") or ""),
            str(payload.get("signed_transaction") or ""),
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(status_code=503, detail="Jupiter swap pilot is not configured.") from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(status_code=503, detail="Jupiter swap execution is temporarily unavailable.") from error


@app.get(
    "/admin/system",
    response_class=HTMLResponse,
    dependencies=[Depends(require_internal_access)],
)
def admin_system() -> str:
    """Display the internal operations console without running a scan."""
    try:
        snapshot = load_current_snapshot()
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="Internal snapshot is temporarily unavailable.") from error

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
        raise HTTPException(status_code=503, detail="Market snapshot is temporarily unavailable.") from error

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


@app.get("/api/markets/{token}/quote")
def market_quote_api(token: str) -> dict[str, object]:
    """Return a validated exact-pool quote without running a scan."""
    from application.live_market_quote_service import (
        LiveMarketQuoteUnavailable,
        fetch_live_market_quote,
    )

    try:
        return fetch_live_market_quote(token)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LiveMarketQuoteUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Exact-pool live price is temporarily unavailable.",
        ) from error

@app.get(
    "/content-control",
    response_class=HTMLResponse,
    dependencies=[Depends(require_internal_access)],
)
def content_control(request: Request) -> str:
    """Display the private founder Content Control Center."""
    if not _content_session_valid(request):
        return render_content_login(configured=content_control_configured())

    try:
        snapshot = load_current_snapshot()
    except (FileNotFoundError, RuntimeError) as error:
        raise HTTPException(status_code=503, detail="Content data is temporarily unavailable.") from error

    return render_content_control(
        snapshot,
        ai_enabled=content_ai_enabled(),
        ai_model=content_ai_model(),
    )


@app.post("/content-control/login", dependencies=[Depends(require_internal_access)])
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


@app.post("/content-control/logout", dependencies=[Depends(require_internal_access)])
def content_control_logout() -> JSONResponse:
    """Clear the founder Content Control Center session."""
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(key=COOKIE_NAME, path="/content-control")
    return response


@app.post("/content-control/generate", dependencies=[Depends(require_internal_access)])
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
        raise HTTPException(status_code=503, detail="Content data is temporarily unavailable.") from error

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
            detail="AI writing service is temporarily unavailable.",
        ) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail="AI writing service is temporarily unavailable.") from error

    return result


@app.get(
    "/api/dashboard",
    dependencies=[Depends(require_internal_access)],
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
            detail="Dashboard data is temporarily unavailable.",
        ) from error


@app.get(
    "/api/system-status",
    dependencies=[Depends(require_internal_access)],
)
def system_status_api() -> dict[str, object]:
    """
    Return operational health without running a market scan.
    """

    return collect_system_dashboard_status()


@app.post(
    "/telegram/send",
    dependencies=[Depends(require_internal_access)],
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
            detail="Telegram delivery is temporarily unavailable.",
        ) from error

    except requests.RequestException as error:

        raise HTTPException(
            status_code=502,
            detail="Telegram delivery is temporarily unavailable.",
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


@app.get("/health/live")
def health_liveness() -> dict[str, str]:
    """Confirm that the application process can serve requests."""
    return health_check()


def readiness_status() -> tuple[bool, dict[str, str]]:
    """Check local resources required to serve the Discovery Terminal."""
    from application.solana_discovery_feed_service import (
        DEFAULT_OUTPUT_DIR,
        DISCOVERY_ARCHIVE_DB,
    )

    project_root = Path(__file__).resolve().parents[1]
    static_ready = (project_root / "static").is_dir()
    discovery_dir = project_root / DEFAULT_OUTPUT_DIR
    collector_ready = (
        (discovery_dir / "state.json").is_file()
        and (discovery_dir / "status.json").is_file()
    )
    archive_ready = (discovery_dir / DISCOVERY_ARCHIVE_DB).is_file()
    checks = {
        "static": "ready" if static_ready else "unavailable",
        "collector": "ready" if collector_ready else "unavailable",
        "archive": "ready" if archive_ready else "unavailable",
    }
    return all(value == "ready" for value in checks.values()), checks


@app.get("/health/ready")
def health_readiness() -> JSONResponse:
    """Return deployment readiness without contacting external providers."""
    ready, checks = readiness_status()
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


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
