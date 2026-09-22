"""Feature-gated product login routes and public-page identity view."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from application.product_auth_provider import (
    ProductAuthDeliveryError,
    ProductAuthUnavailableError,
    ProductAuthVerificationError,
)
from application.product_auth_web import (
    PRODUCT_SESSION_COOKIE,
    delete_product_session_cookie,
    exact_json_object,
    require_same_origin,
    set_product_session_cookie,
)
from application.product_identity_models import ProductPrincipal
from application.product_identity_runtime import (
    build_product_auth_provider,
    build_product_identity_service,
    product_auth_enabled,
    product_identity_configured,
    product_identity_runtime_config,
)
from application.product_identity_service import normalize_email
from presentation.product_auth_presenter import render_product_login_page


router = APIRouter(include_in_schema=False)


@dataclass(frozen=True, slots=True)
class ProductAuthView:
    available: bool
    principal: ProductPrincipal


def _require_product_auth() -> None:
    try:
        enabled = product_auth_enabled()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Product authentication is temporarily unavailable.") from error
    if not enabled:
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        product_identity_runtime_config()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Product authentication is temporarily unavailable.") from error


def product_auth_view(request: Request) -> ProductAuthView:
    """Resolve optional product identity without making the public feed depend on auth."""
    if not product_identity_configured():
        return ProductAuthView(False, ProductPrincipal.guest())
    token = request.cookies.get(PRODUCT_SESSION_COOKIE)
    if not token:
        return ProductAuthView(True, ProductPrincipal.guest())
    try:
        principal = build_product_identity_service().authenticate(token)
    except Exception:
        principal = ProductPrincipal.guest()
    return ProductAuthView(True, principal)


@router.get("/login", response_class=HTMLResponse)
def product_login(request: Request):
    _require_product_auth()
    token = request.cookies.get(PRODUCT_SESSION_COOKIE)
    if token:
        try:
            if build_product_identity_service().authenticate(token).authenticated:
                return RedirectResponse(url="/", status_code=303)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Product authentication is temporarily unavailable.") from error
    return HTMLResponse(render_product_login_page())


@router.post("/auth/otp/request")
async def product_otp_request(request: Request) -> JSONResponse:
    _require_product_auth()
    require_same_origin(request)
    payload = await exact_json_object(request, fields=frozenset({"email"}))
    try:
        email = normalize_email(str(payload["email"]))
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Enter a valid email address.") from error
    try:
        provider = build_product_auth_provider()
        await run_in_threadpool(provider.request_email_otp, email=email)
    except (ProductAuthDeliveryError, ProductAuthUnavailableError) as error:
        raise HTTPException(status_code=503, detail="Sign-in email is temporarily unavailable.") from error
    return JSONResponse(
        {"status": "accepted", "message": "If delivery is available, check your email."},
        status_code=202,
    )


@router.post("/auth/otp/verify")
async def product_otp_verify(request: Request) -> JSONResponse:
    _require_product_auth()
    require_same_origin(request)
    payload = await exact_json_object(request, fields=frozenset({"email", "code"}))
    try:
        email = normalize_email(str(payload["email"]))
        code = str(payload["code"])
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=400, detail="Invalid sign-in request.") from error
    try:
        provider = build_product_auth_provider()
        identity = await run_in_threadpool(provider.verify_email_otp, email=email, code=code)
    except ProductAuthVerificationError as error:
        raise HTTPException(status_code=401, detail="Unable to verify that code.") from error
    except ProductAuthUnavailableError as error:
        raise HTTPException(status_code=503, detail="Product authentication is temporarily unavailable.") from error
    try:
        service = build_product_identity_service()
        issued = await run_in_threadpool(
            service.create_authenticated_session,
            auth_provider=identity.auth_provider,
            auth_subject=identity.auth_subject,
            email=identity.email,
        )
    except Exception as error:
        raise HTTPException(status_code=503, detail="Product authentication is temporarily unavailable.") from error

    response = JSONResponse({"status": "ok", "redirect": "/"})
    set_product_session_cookie(
        response,
        request,
        token=issued.token,
        expires_at=issued.expires_at,
    )
    return response


@router.post("/logout")
async def product_logout(request: Request) -> JSONResponse:
    _require_product_auth()
    require_same_origin(request)
    token = request.cookies.get(PRODUCT_SESSION_COOKIE)
    status_code = 200
    if token:
        try:
            service = build_product_identity_service()
            await run_in_threadpool(service.logout, token)
        except Exception:
            status_code = 503
    response = JSONResponse(
        {"status": "ok" if status_code == 200 else "unavailable"},
        status_code=status_code,
    )
    delete_product_session_cookie(response, request)
    return response
