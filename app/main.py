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
- Supervise the optional one-shot discovery collector scheduler

This module does NOT:
- run scans when pages are opened
- calculate market decisions
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
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

from application.token_workspace_rate_limit import (
    TokenWorkspaceRateLimitMiddleware,
    configure_rate_limit_store,
)
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool

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
from application.solana_discovery_feed_service import (
    load_solana_discovery_engine_feed,
    load_solana_discovery_feed,
)
from application.jupiter_market_feed_service import (
    load_jupiter_ranked_market_feeds,
    load_jupiter_recent_feed,
)
from application.solana_discovery_token_service import (
    load_solana_discovery_live_candles,
    load_solana_discovery_token,
    load_solana_discovery_transactions,
)
from application.recent_token_workspace_service import (
    RecentWorkspaceUnavailable,
    is_recent_token_workspace_eligible,
    load_recent_execution_feed,
    load_recent_execution_record,
    load_recent_live_candles,
    load_recent_token_workspace,
    load_recent_transactions,
)
from application.organic_flow_token_workspace_service import (
    OrganicFlowWorkspaceUnavailable,
    is_organic_flow_token_workspace_eligible,
    load_organic_flow_execution_feed,
    load_organic_flow_execution_record,
    load_organic_flow_live_candles,
    load_organic_flow_token_workspace,
    load_organic_flow_transactions,
)
from application.top_traded_token_workspace_service import (
    TopTradedWorkspaceUnavailable,
    is_top_traded_token_workspace_eligible,
    load_top_traded_execution_feed,
    load_top_traded_execution_record,
    load_top_traded_live_candles,
    load_top_traded_token_workspace,
    load_top_traded_transactions,
)
from application.trending_token_workspace_service import (
    TrendingWorkspaceUnavailable,
    is_trending_token_workspace_eligible,
    load_trending_candidate_feed,
    load_trending_execution_feed,
    load_trending_execution_record,
    load_trending_live_candles,
    load_trending_token_workspace,
    load_trending_transactions,
)
from application.solana_wallet_balance_service import (
    SolanaWalletBalanceRejected,
    SolanaWalletBalanceUnavailable,
    load_solana_wallet_balance,
    validate_wallet_trade_amount,
)

from application.telegram_notifier import (
    send_telegram_alert,
)
from application.production_security import (
    ApplicationBoundaryMiddleware,
    ProductionLoggingMiddleware,
    SecurityHeadersMiddleware,
    allowed_hosts,
    application_host,
    application_port,
    configure_production_logging,
    production_mode,
    require_internal_access,
    safe_jupiter_error_detail,
    trusted_proxy_headers,
)
from application.discovery_storage import discovery_storage_dir, validate_production_runtime
from application.production_readiness import (
    collector_fresh,
    collector_storage_ready,
    discovery_archive_ready,
    production_configuration_ready,
    validate_production_configuration,
)
from application.collector_scheduler import CollectorScheduler, collector_enabled
from application.jupiter_swap_service import configure_jupiter_pending_store
from application.jupiter_pending_store import JupiterPendingStoreUnavailable

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
    load_solana_discovery_presenter_context,
    render_solana_discovery_page,
)
from presentation.dexsato_solana_discovery_token_presenter import (
    render_solana_discovery_token_page,
)
from presentation.dexsato_market_feed_token_presenter import (
    render_organic_flow_token_page,
    render_recent_token_page,
    render_top_traded_token_page,
    render_trending_token_page,
)

render_founder_snapshot_dashboard = render_user_dashboard


APP_TITLE = "DexSato V1"

APP_VERSION = "1.0.0"

HOST = application_host()

PORT = application_port()

configure_production_logging()

validate_production_runtime()

validate_production_configuration()

configure_jupiter_pending_store()

configure_rate_limit_store()


@asynccontextmanager
async def application_lifespan(application: FastAPI):
    """Own the optional collector scheduler for the application lifetime."""
    scheduler = CollectorScheduler.from_environment()
    application.state.collector_scheduler = scheduler
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    lifespan=application_lifespan,
)

# Middleware registration order matters: Starlette executes the last-added
# middleware outermost. Keep SecurityHeaders outermost and enforce the request
# body boundary before TokenWorkspaceRateLimitMiddleware reads JSON bodies.
app.add_middleware(TokenWorkspaceRateLimitMiddleware)
app.add_middleware(ApplicationBoundaryMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())
app.add_middleware(ProductionLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

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
    from application.founder_snapshot_service import read_latest_snapshot

    return read_latest_snapshot()


def _collect_system_dashboard_status() -> dict[str, object]:
    """Load founder system-health dependencies only when requested."""
    from application.system_health_dashboard import (
        collect_system_dashboard_status as _collect_status,
    )

    return _collect_status()


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


def _load_discovery_market_feeds() -> dict[str, dict[str, object]]:
    """Load shared ranked feeds and independent Recent concurrently."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        ranked_future = executor.submit(load_jupiter_ranked_market_feeds)
        recent_future = executor.submit(load_jupiter_recent_feed)
        ranked = ranked_future.result()
        return {
            "trending": ranked["trending"],
            "top_traded": ranked["top_traded"],
            "organic_flow": ranked["organic_flow"],
            "recent": recent_future.result(),
        }


def _load_discovery_page_context() -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """Overlap independent market-feed and presenter-metric refresh work."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        market_future = executor.submit(_load_discovery_market_feeds)
        presenter_future = executor.submit(load_solana_discovery_presenter_context)
        return market_future.result(), presenter_future.result()


# LIVE-02 — Solana Discovery is the public app landing experience.
@app.get(
    "/",
    response_class=HTMLResponse,
)
def app_home() -> str:
    """Display Solana Discovery as the DexSato main app."""
    market_feeds, presenter_context = _load_discovery_page_context()
    return render_solana_discovery_page(
        load_solana_discovery_feed(view="rolling", page=1, page_size=25, query=""),
        trending=market_feeds["trending"],
        top_traded=market_feeds["top_traded"],
        organic_flow=market_feeds["organic_flow"],
        recent=market_feeds["recent"],
        presenter_context=presenter_context,
    )


# TEMP-HIDE-MAJOR-ASSETS-01 - keep the legacy handler but do not expose a route.
def major_assets() -> str:
    """Preserve the previous Major Assets dashboard as a secondary route."""
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

    system_status = _collect_system_dashboard_status()

    return render_founder_snapshot_dashboard(
        snapshot,
        system_status=system_status,
    )


@app.get(
    "/discovery/solana",
    response_class=HTMLResponse,
)
def solana_discovery(view: str = "rolling", page: int = 1, q: str = "") -> str:
    """Display the read-only Solana Discovery D1 prototype."""
    market_feeds, presenter_context = _load_discovery_page_context()
    return render_solana_discovery_page(
        load_solana_discovery_feed(view=view, page=page, page_size=25, query=q),
        trending=market_feeds["trending"],
        top_traded=market_feeds["top_traded"],
        organic_flow=market_feeds["organic_flow"],
        recent=market_feeds["recent"],
        presenter_context=presenter_context,
    )


@app.get(
    "/discovery/solana/{token_address}",
    response_class=HTMLResponse,
)
def solana_discovery_token(token_address: str) -> str:
    """Display one observed exact-token workspace and its controlled swap flow."""
    detail = load_solana_discovery_token(token_address)
    if detail is None:
        raise HTTPException(status_code=404, detail="Qualified discovery token is not available.")
    feed = load_solana_discovery_feed()
    return render_solana_discovery_token_page(detail, feed=feed)


@app.get(
    "/market/recent/{token_address}",
    response_class=HTMLResponse,
)
def recent_token_workspace(token_address: str) -> str:
    """Display one current/recent eligible Jupiter Recent token."""
    try:
        loaded = load_recent_token_workspace(token_address)
    except RecentWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Recent market feed is temporarily unavailable.",
        ) from error
    if loaded is None:
        raise HTTPException(
            status_code=404,
            detail="Recent token is not available in the eligible feed window.",
        )
    detail, feed = loaded
    return render_recent_token_page(detail, feed=feed)


@app.get("/api/market/recent/{token_address}/candles")
def recent_token_candles(
    token_address: str,
    timeframe: str = "5m",
) -> dict[str, object]:
    try:
        payload = load_recent_live_candles(token_address, timeframe)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RecentWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Recent market feed is temporarily unavailable.",
        ) from error
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Recent candle data is temporarily unavailable.",
        ) from error
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Recent token is not available.",
        )
    return payload


@app.get("/api/market/recent/{token_address}/transactions")
def recent_token_transactions(token_address: str) -> dict[str, object]:
    try:
        payload = load_recent_transactions(token_address)
    except RecentWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Recent market feed is temporarily unavailable.",
        ) from error
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Recent transaction data is temporarily unavailable.",
        ) from error
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Recent token is not available.",
        )
    return payload


@app.get(
    "/market/organic-flow/{token_address}",
    response_class=HTMLResponse,
)
def organic_flow_token_workspace(token_address: str) -> str:
    """Display one current/recent eligible Jupiter Organic Flow token."""
    try:
        loaded = load_organic_flow_token_workspace(token_address)
    except OrganicFlowWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Organic Flow market feed is temporarily unavailable.",
        ) from error
    if loaded is None:
        raise HTTPException(
            status_code=404,
            detail="Organic Flow token is not available in the eligible feed window.",
        )
    detail, feed = loaded
    return render_organic_flow_token_page(detail, feed=feed)


@app.get("/api/market/organic-flow/{token_address}/candles")
def organic_flow_token_candles(
    token_address: str,
    timeframe: str = "5m",
) -> dict[str, object]:
    try:
        payload = load_organic_flow_live_candles(token_address, timeframe)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except OrganicFlowWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Organic Flow market feed is temporarily unavailable.",
        ) from error
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Organic Flow candle data is temporarily unavailable.",
        ) from error
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Organic Flow token is not available.",
        )
    return payload


@app.get("/api/market/organic-flow/{token_address}/transactions")
def organic_flow_token_transactions(token_address: str) -> dict[str, object]:
    try:
        payload = load_organic_flow_transactions(token_address)
    except OrganicFlowWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Organic Flow market feed is temporarily unavailable.",
        ) from error
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Organic Flow transaction data is temporarily unavailable.",
        ) from error
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Organic Flow token is not available.",
        )
    return payload


@app.get(
    "/market/top-traded/{token_address}",
    response_class=HTMLResponse,
)
def top_traded_token_workspace(token_address: str) -> str:
    """Display one current/recent eligible Jupiter Top Traded token."""
    try:
        loaded = load_top_traded_token_workspace(token_address)
    except TopTradedWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Top Traded market feed is temporarily unavailable.",
        ) from error
    if loaded is None:
        raise HTTPException(
            status_code=404,
            detail="Top Traded token is not available in the eligible feed window.",
        )
    detail, feed = loaded
    return render_top_traded_token_page(detail, feed=feed)


@app.get("/api/market/top-traded/{token_address}/candles")
def top_traded_token_candles(
    token_address: str,
    timeframe: str = "5m",
) -> dict[str, object]:
    try:
        payload = load_top_traded_live_candles(token_address, timeframe)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except TopTradedWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Top Traded market feed is temporarily unavailable.",
        ) from error
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Top Traded candle data is temporarily unavailable.",
        ) from error
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Top Traded token is not available.",
        )
    return payload


@app.get("/api/market/top-traded/{token_address}/transactions")
def top_traded_token_transactions(token_address: str) -> dict[str, object]:
    try:
        payload = load_top_traded_transactions(token_address)
    except TopTradedWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Top Traded market feed is temporarily unavailable.",
        ) from error
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Top Traded transaction data is temporarily unavailable.",
        ) from error
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="Top Traded token is not available.",
        )
    return payload


@app.get(
    "/market/trending/{token_address}",
    response_class=HTMLResponse,
)
def trending_token_workspace(token_address: str) -> str:
    """Display one current Jupiter Trending token in a separate workspace."""
    try:
        loaded = load_trending_token_workspace(token_address)
    except TrendingWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Trending market feed is temporarily unavailable.",
        ) from error
    if loaded is None:
        raise HTTPException(
            status_code=404,
            detail="Trending token is not available in the current eligible feed.",
        )
    detail, feed = loaded
    return render_trending_token_page(detail, feed=feed)


@app.get("/api/market/trending/{token_address}/candles")
def trending_token_candles(
    token_address: str,
    timeframe: str = "5m",
) -> dict[str, object]:
    try:
        payload = load_trending_live_candles(token_address, timeframe)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except TrendingWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Trending market feed is temporarily unavailable.",
        ) from error
    except (requests.RequestException, RuntimeError, TypeError) as error:
        raise HTTPException(
            status_code=503,
            detail="Trending candle data is temporarily unavailable.",
        ) from error
    if payload is None:
        raise HTTPException(status_code=404, detail="Trending token is not available.")
    return payload


@app.get("/api/market/trending/{token_address}/transactions")
def trending_token_transactions(token_address: str) -> dict[str, object]:
    try:
        payload = load_trending_transactions(token_address)
    except TrendingWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Trending market feed is temporarily unavailable.",
        ) from error
    except (requests.RequestException, RuntimeError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Trending transaction data is temporarily unavailable.",
        ) from error
    if payload is None:
        raise HTTPException(status_code=404, detail="Trending token is not available.")
    return payload


@app.get("/api/discovery/solana/engine")
def solana_discovery_engine() -> dict[str, object]:
    """Return the lightweight qualified-token feed used by Discovery Engine."""
    return load_solana_discovery_engine_feed(limit=25)

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


def _require_recent_market_token(token_address: str) -> None:
    """Require live or recently displayed Recent workspace eligibility."""
    try:
        eligible = is_recent_token_workspace_eligible(token_address)
    except RecentWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Recent market feed is temporarily unavailable.",
        ) from error

    if not eligible:
        raise HTTPException(
            status_code=404,
            detail="Token is not available in the Recent workspace window.",
        )


@app.get("/api/market/recent/{token_address}/jupiter-quote")
def recent_jupiter_quote(
    token_address: str,
    amount_sol: str = "0.1",
    amount: str | None = None,
    side: str = "buy",
) -> dict[str, object]:
    """Return the production Jupiter quote contract for a Recent token."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
        fetch_jupiter_quote,
    )

    _require_recent_market_token(token_address)
    try:
        feed = load_recent_execution_feed(token_address)
        return fetch_jupiter_quote(
            token_address,
            amount if amount is not None else amount_sol,
            side=side,
            feed=feed,
        )
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


@app.get("/api/market/recent/{token_address}/wallet-balance")
async def recent_wallet_balance(
    token_address: str,
    wallet_address: str,
) -> dict[str, object]:
    """Return read-only balances for a Recent token."""
    await run_in_threadpool(_require_recent_market_token, token_address)
    try:
        feed = load_recent_execution_feed(token_address)
        return await run_in_threadpool(
            load_solana_wallet_balance,
            token_address,
            wallet_address,
            record_loader=lambda address: load_recent_execution_record(
                address,
                feed=feed,
            ),
        )
    except SolanaWalletBalanceRejected as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/market/recent/{token_address}/jupiter-order")
async def recent_jupiter_order(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Prepare the production Jupiter order through a Recent route."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
    )
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapPendingLimit,
        JupiterSwapRejected,
        prepare_jupiter_swap,
    )

    await run_in_threadpool(_require_recent_market_token, token_address)
    payload = await _jupiter_swap_body(
        request,
        {"amount", "amount_sol", "side", "wallet_address", "risk_acknowledged"},
    )
    trade_amount = (
        payload.get("amount")
        if payload.get("amount") is not None
        else payload.get("amount_sol")
    )
    wallet_address = str(payload.get("wallet_address") or "")
    side = str(payload.get("side") or "buy")

    try:
        feed = load_recent_execution_feed(token_address)
        balance = await run_in_threadpool(
            load_solana_wallet_balance,
            token_address,
            wallet_address,
            record_loader=lambda address: load_recent_execution_record(
                address,
                feed=feed,
            ),
        )
        await run_in_threadpool(
            validate_wallet_trade_amount,
            balance,
            side,
            trade_amount,
        )
        return await run_in_threadpool(
            prepare_jupiter_swap,
            token_address,
            trade_amount,
            wallet_address,
            side=side,
            risk_acknowledged=payload.get("risk_acknowledged") is True,
            feed=feed,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except JupiterSwapPendingLimit as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Swap coordination is temporarily unavailable.",
        ) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap pilot is not configured.",
        ) from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail=safe_jupiter_error_detail(error),
        ) from error


@app.post("/api/market/recent/{token_address}/jupiter-execute")
async def recent_jupiter_execute(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Relay a wallet-approved Jupiter transaction through Recent."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
    )
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapRejected,
        execute_jupiter_swap,
    )

    await run_in_threadpool(_require_recent_market_token, token_address)
    payload = await _jupiter_swap_body(
        request,
        {"request_id", "wallet_address", "signed_transaction"},
    )
    try:
        feed = load_recent_execution_feed(token_address)
        return await run_in_threadpool(
            execute_jupiter_swap,
            token_address,
            str(payload.get("request_id") or ""),
            str(payload.get("wallet_address") or ""),
            str(payload.get("signed_transaction") or ""),
            feed=feed,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Swap coordination is temporarily unavailable.",
        ) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap pilot is not configured.",
        ) from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap execution is temporarily unavailable.",
        ) from error


def _require_organic_flow_market_token(token_address: str) -> None:
    """Require live or recently displayed Organic Flow workspace eligibility."""
    try:
        eligible = is_organic_flow_token_workspace_eligible(token_address)
    except OrganicFlowWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Organic Flow market feed is temporarily unavailable.",
        ) from error

    if not eligible:
        raise HTTPException(
            status_code=404,
            detail="Token is not available in the Organic Flow workspace window.",
        )


@app.get("/api/market/organic-flow/{token_address}/jupiter-quote")
def organic_flow_jupiter_quote(
    token_address: str,
    amount_sol: str = "0.1",
    amount: str | None = None,
    side: str = "buy",
) -> dict[str, object]:
    """Return the production Jupiter quote contract for an Organic Flow token."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
        fetch_jupiter_quote,
    )

    _require_organic_flow_market_token(token_address)
    try:
        feed = load_organic_flow_execution_feed(token_address)
        return fetch_jupiter_quote(
            token_address,
            amount if amount is not None else amount_sol,
            side=side,
            feed=feed,
        )
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


@app.get("/api/market/organic-flow/{token_address}/wallet-balance")
async def organic_flow_wallet_balance(
    token_address: str,
    wallet_address: str,
) -> dict[str, object]:
    """Return read-only balances for an Organic Flow token."""
    await run_in_threadpool(_require_organic_flow_market_token, token_address)
    try:
        feed = load_organic_flow_execution_feed(token_address)
        return await run_in_threadpool(
            load_solana_wallet_balance,
            token_address,
            wallet_address,
            record_loader=lambda address: load_organic_flow_execution_record(
                address,
                feed=feed,
            ),
        )
    except SolanaWalletBalanceRejected as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/market/organic-flow/{token_address}/jupiter-order")
async def organic_flow_jupiter_order(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Prepare the production Jupiter order through an Organic Flow route."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
    )
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapPendingLimit,
        JupiterSwapRejected,
        prepare_jupiter_swap,
    )

    await run_in_threadpool(_require_organic_flow_market_token, token_address)
    payload = await _jupiter_swap_body(
        request,
        {"amount", "amount_sol", "side", "wallet_address", "risk_acknowledged"},
    )
    trade_amount = (
        payload.get("amount")
        if payload.get("amount") is not None
        else payload.get("amount_sol")
    )
    wallet_address = str(payload.get("wallet_address") or "")
    side = str(payload.get("side") or "buy")

    try:
        feed = load_organic_flow_execution_feed(token_address)
        balance = await run_in_threadpool(
            load_solana_wallet_balance,
            token_address,
            wallet_address,
            record_loader=lambda address: load_organic_flow_execution_record(
                address,
                feed=feed,
            ),
        )
        await run_in_threadpool(
            validate_wallet_trade_amount,
            balance,
            side,
            trade_amount,
        )
        return await run_in_threadpool(
            prepare_jupiter_swap,
            token_address,
            trade_amount,
            wallet_address,
            side=side,
            risk_acknowledged=payload.get("risk_acknowledged") is True,
            feed=feed,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except JupiterSwapPendingLimit as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Swap coordination is temporarily unavailable.",
        ) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap pilot is not configured.",
        ) from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail=safe_jupiter_error_detail(error),
        ) from error


@app.post("/api/market/organic-flow/{token_address}/jupiter-execute")
async def organic_flow_jupiter_execute(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Relay a wallet-approved Jupiter transaction through Organic Flow."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
    )
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapRejected,
        execute_jupiter_swap,
    )

    await run_in_threadpool(_require_organic_flow_market_token, token_address)
    payload = await _jupiter_swap_body(
        request,
        {"request_id", "wallet_address", "signed_transaction"},
    )
    try:
        feed = load_organic_flow_execution_feed(token_address)
        return await run_in_threadpool(
            execute_jupiter_swap,
            token_address,
            str(payload.get("request_id") or ""),
            str(payload.get("wallet_address") or ""),
            str(payload.get("signed_transaction") or ""),
            feed=feed,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Swap coordination is temporarily unavailable.",
        ) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap pilot is not configured.",
        ) from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap execution is temporarily unavailable.",
        ) from error


def _require_top_traded_market_token(token_address: str) -> None:
    """Require live or recently displayed Top Traded workspace eligibility."""
    try:
        eligible = is_top_traded_token_workspace_eligible(token_address)
    except TopTradedWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Top Traded market feed is temporarily unavailable.",
        ) from error

    if not eligible:
        raise HTTPException(
            status_code=404,
            detail="Token is not available in the Top Traded workspace window.",
        )


@app.get("/api/market/top-traded/{token_address}/jupiter-quote")
def top_traded_jupiter_quote(
    token_address: str,
    amount_sol: str = "0.1",
    amount: str | None = None,
    side: str = "buy",
) -> dict[str, object]:
    """Return the production Jupiter quote contract for a Top Traded token."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
        fetch_jupiter_quote,
    )

    _require_top_traded_market_token(token_address)
    try:
        feed = load_top_traded_execution_feed(token_address)
        return fetch_jupiter_quote(
            token_address,
            amount if amount is not None else amount_sol,
            side=side,
            feed=feed,
        )
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


@app.get("/api/market/top-traded/{token_address}/wallet-balance")
async def top_traded_wallet_balance(
    token_address: str,
    wallet_address: str,
) -> dict[str, object]:
    """Return read-only balances for a Top Traded token."""
    await run_in_threadpool(_require_top_traded_market_token, token_address)
    try:
        feed = load_top_traded_execution_feed(token_address)
        return await run_in_threadpool(
            load_solana_wallet_balance,
            token_address,
            wallet_address,
            record_loader=lambda address: load_top_traded_execution_record(
                address,
                feed=feed,
            ),
        )
    except SolanaWalletBalanceRejected as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/market/top-traded/{token_address}/jupiter-order")
async def top_traded_jupiter_order(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Prepare the production Jupiter order through a Top Traded route."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
    )
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapPendingLimit,
        JupiterSwapRejected,
        prepare_jupiter_swap,
    )

    await run_in_threadpool(_require_top_traded_market_token, token_address)
    payload = await _jupiter_swap_body(
        request,
        {"amount", "amount_sol", "side", "wallet_address", "risk_acknowledged"},
    )
    trade_amount = (
        payload.get("amount")
        if payload.get("amount") is not None
        else payload.get("amount_sol")
    )
    wallet_address = str(payload.get("wallet_address") or "")
    side = str(payload.get("side") or "buy")

    try:
        feed = load_top_traded_execution_feed(token_address)
        balance = await run_in_threadpool(
            load_solana_wallet_balance,
            token_address,
            wallet_address,
            record_loader=lambda address: load_top_traded_execution_record(
                address,
                feed=feed,
            ),
        )
        await run_in_threadpool(
            validate_wallet_trade_amount,
            balance,
            side,
            trade_amount,
        )
        return await run_in_threadpool(
            prepare_jupiter_swap,
            token_address,
            trade_amount,
            wallet_address,
            side=side,
            risk_acknowledged=payload.get("risk_acknowledged") is True,
            feed=feed,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except JupiterSwapPendingLimit as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Swap coordination is temporarily unavailable.",
        ) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap pilot is not configured.",
        ) from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail=safe_jupiter_error_detail(error),
        ) from error


@app.post("/api/market/top-traded/{token_address}/jupiter-execute")
async def top_traded_jupiter_execute(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Relay a wallet-approved Jupiter transaction through Top Traded."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
    )
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapRejected,
        execute_jupiter_swap,
    )

    await run_in_threadpool(_require_top_traded_market_token, token_address)
    payload = await _jupiter_swap_body(
        request,
        {"request_id", "wallet_address", "signed_transaction"},
    )
    try:
        feed = load_top_traded_execution_feed(token_address)
        return await run_in_threadpool(
            execute_jupiter_swap,
            token_address,
            str(payload.get("request_id") or ""),
            str(payload.get("wallet_address") or ""),
            str(payload.get("signed_transaction") or ""),
            feed=feed,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Swap coordination is temporarily unavailable.",
        ) from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap pilot is not configured.",
        ) from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Jupiter swap execution is temporarily unavailable.",
        ) from error


def _require_trending_market_token(token_address: str) -> None:
    """Require live or recently displayed Trending workspace eligibility."""
    try:
        eligible = is_trending_token_workspace_eligible(token_address)
    except TrendingWorkspaceUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Trending market feed is temporarily unavailable.",
        ) from error

    if not eligible:
        raise HTTPException(
            status_code=404,
            detail="Token is not available in the Trending workspace window.",
        )


@app.get("/api/market/trending/{token_address}/jupiter-quote")
def trending_jupiter_quote(
    token_address: str,
    amount_sol: str = "0.1",
    amount: str | None = None,
    side: str = "buy",
) -> dict[str, object]:
    """Return the production Jupiter quote contract for a current Trending token."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
        fetch_jupiter_quote,
    )

    _require_trending_market_token(token_address)
    try:
        feed = load_trending_execution_feed(token_address)
        return fetch_jupiter_quote(
            token_address,
            amount if amount is not None else amount_sol,
            side=side,
            feed=feed,
        )
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


@app.get("/api/market/trending/{token_address}/wallet-balance")
async def trending_wallet_balance(
    token_address: str,
    wallet_address: str,
) -> dict[str, object]:
    """Return read-only balances for a current Trending token."""
    await run_in_threadpool(_require_trending_market_token, token_address)
    try:
        feed = load_trending_execution_feed(token_address)
        return await run_in_threadpool(
            load_solana_wallet_balance,
            token_address,
            wallet_address,
            record_loader=lambda address: load_trending_execution_record(
                address,
                feed=feed,
            ),
        )
    except SolanaWalletBalanceRejected as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/market/trending/{token_address}/jupiter-order")
async def trending_jupiter_order(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Prepare the same production Jupiter order through a Trending route."""
    from application.jupiter_quote_service import JupiterQuoteNotConfigured, JupiterQuoteUnavailable
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapPendingLimit,
        JupiterSwapRejected,
        prepare_jupiter_swap,
    )

    await run_in_threadpool(_require_trending_market_token, token_address)
    payload = await _jupiter_swap_body(
        request,
        {"amount", "amount_sol", "side", "wallet_address", "risk_acknowledged"},
    )
    trade_amount = (
        payload.get("amount")
        if payload.get("amount") is not None
        else payload.get("amount_sol")
    )
    wallet_address = str(payload.get("wallet_address") or "")
    side = str(payload.get("side") or "buy")

    try:
        feed = load_trending_execution_feed(token_address)
        balance = await run_in_threadpool(
            load_solana_wallet_balance,
            token_address,
            wallet_address,
            record_loader=lambda address: load_trending_execution_record(
                address,
                feed=feed,
            ),
        )
        await run_in_threadpool(
            validate_wallet_trade_amount, balance, side, trade_amount,
        )
        return await run_in_threadpool(
            prepare_jupiter_swap,
            token_address,
            trade_amount,
            wallet_address,
            side=side,
            risk_acknowledged=payload.get("risk_acknowledged") is True,
            feed=feed,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except JupiterSwapPendingLimit as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(status_code=503, detail="Swap coordination is temporarily unavailable.") from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(status_code=503, detail="Jupiter swap pilot is not configured.") from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(status_code=503, detail=safe_jupiter_error_detail(error)) from error


@app.post("/api/market/trending/{token_address}/jupiter-execute")
async def trending_jupiter_execute(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Relay a wallet-approved Jupiter transaction through the Trending route."""
    from application.jupiter_quote_service import JupiterQuoteNotConfigured, JupiterQuoteUnavailable
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapRejected,
        execute_jupiter_swap,
    )

    await run_in_threadpool(_require_trending_market_token, token_address)
    payload = await _jupiter_swap_body(
        request,
        {"request_id", "wallet_address", "signed_transaction"},
    )
    try:
        feed = load_trending_execution_feed(token_address)
        return await run_in_threadpool(
            execute_jupiter_swap,
            token_address,
            str(payload.get("request_id") or ""),
            str(payload.get("wallet_address") or ""),
            str(payload.get("signed_transaction") or ""),
            feed=feed,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(status_code=503, detail="Swap coordination is temporarily unavailable.") from error
    except JupiterQuoteNotConfigured as error:
        raise HTTPException(status_code=503, detail="Jupiter swap pilot is not configured.") from error
    except JupiterQuoteUnavailable as error:
        raise HTTPException(status_code=503, detail="Jupiter swap execution is temporarily unavailable.") from error


@app.get("/api/discovery/solana/{token_address}/jupiter-quote")
def solana_discovery_jupiter_quote(
    token_address: str,
    amount_sol: str = "0.1",
    amount: str | None = None,
    side: str = "buy",
) -> dict[str, object]:
    """Return a quote-only Jupiter order for a bounded buy or sell."""
    from application.jupiter_quote_service import (
        JupiterQuoteNotConfigured,
        JupiterQuoteUnavailable,
        fetch_jupiter_quote,
    )

    try:
        return fetch_jupiter_quote(
            token_address,
            amount if amount is not None else amount_sol,
            side=side,
        )
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


@app.get("/api/discovery/solana/{token_address}/wallet-balance")
async def solana_discovery_wallet_balance(
    token_address: str,
    wallet_address: str,
) -> dict[str, object]:
    """Return read-only SOL and exact-token balances for percentage controls."""
    try:
        return await run_in_threadpool(
            load_solana_wallet_balance, token_address, wallet_address,
        )
    except SolanaWalletBalanceRejected as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/discovery/solana/{token_address}/jupiter-order")
async def solana_discovery_jupiter_order(
    token_address: str,
    request: Request,
) -> dict[str, object]:
    """Prepare an unsigned transaction after an explicit mainnet risk acknowledgement."""
    from application.jupiter_quote_service import JupiterQuoteNotConfigured, JupiterQuoteUnavailable
    from application.jupiter_swap_service import (
        JupiterSwapExpired,
        JupiterSwapPendingLimit,
        JupiterSwapRejected,
        prepare_jupiter_swap,
    )

    payload = await _jupiter_swap_body(
        request,
        {"amount", "amount_sol", "side", "wallet_address", "risk_acknowledged"},
    )
    trade_amount = (
        payload.get("amount")
        if payload.get("amount") is not None
        else payload.get("amount_sol")
    )
    wallet_address = str(payload.get("wallet_address") or "")
    side = str(payload.get("side") or "buy")
    try:
        balance = await run_in_threadpool(
            load_solana_wallet_balance, token_address, wallet_address,
        )
        await run_in_threadpool(
            validate_wallet_trade_amount, balance, side, trade_amount,
        )
        return await run_in_threadpool(
            prepare_jupiter_swap,
            token_address,
            trade_amount,
            wallet_address,
            side=side,
            risk_acknowledged=payload.get("risk_acknowledged") is True,
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except JupiterSwapPendingLimit as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SolanaWalletBalanceUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(status_code=503, detail="Swap coordination is temporarily unavailable.") from error
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
        return await run_in_threadpool(
            execute_jupiter_swap,
            token_address,
            str(payload.get("request_id") or ""),
            str(payload.get("wallet_address") or ""),
            str(payload.get("signed_transaction") or ""),
        )
    except JupiterSwapExpired as error:
        raise HTTPException(status_code=410, detail=str(error)) from error
    except (JupiterSwapRejected, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except JupiterPendingStoreUnavailable as error:
        raise HTTPException(status_code=503, detail="Swap coordination is temporarily unavailable.") from error
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
        system_status=_collect_system_dashboard_status(),
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

    return _collect_system_dashboard_status()


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
    discovery_dir = discovery_storage_dir(DEFAULT_OUTPUT_DIR)
    collector_ready = collector_storage_ready(discovery_dir)
    archive_ready = discovery_archive_ready(discovery_dir, DISCOVERY_ARCHIVE_DB)
    enabled = collector_enabled()
    fresh = collector_fresh(discovery_dir) if enabled else True
    configuration_ready = production_configuration_ready()
    checks = {
        "static": "ready" if static_ready else "unavailable",
        "collector_storage": "ready" if collector_ready else "unavailable",
        "discovery_archive": "ready" if archive_ready else "unavailable",
        "collector_fresh": "ready" if fresh else "stale",
        "configuration": "ready" if configuration_ready else "unavailable",
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
        access_log=not production_mode(),
    )


if __name__ == "__main__":

    run()
