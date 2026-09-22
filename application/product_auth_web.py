"""HTTP boundary helpers for the feature-gated DexSato product identity flow."""

from __future__ import annotations

from datetime import UTC, datetime
import hmac
import math
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import Response

from application.production_security import production_mode, trusted_proxy_headers


PRODUCT_SESSION_COOKIE = "dexsato_product_session"
PRODUCT_SESSION_COOKIE_PATH = "/"
PRODUCT_SESSION_COOKIE_SAMESITE = "lax"


def product_cookie_secure(request: Request) -> bool:
    """Require Secure in production and honor HTTPS only from trusted proxies."""
    if production_mode() or request.url.scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "")
    return trusted_proxy_headers() and forwarded.casefold() == "https"


def require_same_origin(request: Request) -> None:
    """Reject login CSRF before any OTP provider or session work occurs."""
    origin = request.headers.get("origin", "").strip()
    host = request.headers.get("host", "").strip().casefold()
    if not origin or not host:
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")

    parsed = urlsplit(origin)
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")

    expected_scheme = "https" if product_cookie_secure(request) else request.url.scheme.casefold()
    supplied = f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}"
    expected = f"{expected_scheme}://{host}"
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")


async def exact_json_object(request: Request, *, fields: frozenset[str]) -> dict[str, object]:
    content_type = request.headers.get("content-type", "").partition(";")[0].strip().casefold()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="A JSON request is required.")
    try:
        payload = await request.json()
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid authentication request.") from error
    if not isinstance(payload, dict) or set(payload) != fields:
        raise HTTPException(status_code=400, detail="Invalid authentication request.")
    return payload


def set_product_session_cookie(response: Response, request: Request, *, token: str, expires_at: datetime) -> None:
    now = datetime.now(UTC)
    max_age = max(1, int(math.ceil((expires_at.astimezone(UTC) - now).total_seconds())))
    response.set_cookie(
        key=PRODUCT_SESSION_COOKIE,
        value=token,
        max_age=max_age,
        expires=expires_at,
        httponly=True,
        secure=product_cookie_secure(request),
        samesite=PRODUCT_SESSION_COOKIE_SAMESITE,
        path=PRODUCT_SESSION_COOKIE_PATH,
    )


def delete_product_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=PRODUCT_SESSION_COOKIE,
        path=PRODUCT_SESSION_COOKIE_PATH,
        secure=product_cookie_secure(request),
        httponly=True,
        samesite=PRODUCT_SESSION_COOKIE_SAMESITE,
    )
