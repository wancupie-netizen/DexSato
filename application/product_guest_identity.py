"""Stable guest identity helpers for public DexSato product surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.responses import Response

from application.product_auth_web import product_cookie_secure


PRODUCT_GUEST_COOKIE = "dexsato_product_guest"
PRODUCT_GUEST_COOKIE_PATH = "/"
PRODUCT_GUEST_COOKIE_SAMESITE = "lax"
PRODUCT_GUEST_COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class ProductGuestIdentity:
    guest_id: UUID
    cookie_required: bool


def _canonical_guest_uuid(value: object) -> UUID | None:
    """Return a UUID only when the cookie value is already canonical."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return None
    if str(parsed) != value:
        return None
    return parsed


def resolve_product_guest_identity(
    request: Request,
    *,
    uuid_factory: Callable[[], UUID] = uuid4,
) -> ProductGuestIdentity:
    """Reuse a canonical guest UUID or mint one without mutating the response."""
    existing = _canonical_guest_uuid(request.cookies.get(PRODUCT_GUEST_COOKIE))
    if existing is not None:
        return ProductGuestIdentity(existing, False)

    generated = uuid_factory()
    if not isinstance(generated, UUID):
        raise TypeError("Guest UUID factory must return UUID.")
    return ProductGuestIdentity(generated, True)


def set_product_guest_cookie(
    response: Response,
    request: Request,
    *,
    guest_id: UUID,
) -> None:
    """Persist a host-only guest UUID using the product cookie security policy."""
    if not isinstance(guest_id, UUID):
        raise TypeError("Guest identity must be UUID.")
    response.set_cookie(
        key=PRODUCT_GUEST_COOKIE,
        value=str(guest_id),
        max_age=PRODUCT_GUEST_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=product_cookie_secure(request),
        samesite=PRODUCT_GUEST_COOKIE_SAMESITE,
        path=PRODUCT_GUEST_COOKIE_PATH,
    )
