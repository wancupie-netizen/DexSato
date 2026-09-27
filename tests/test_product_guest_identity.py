from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from fastapi.responses import JSONResponse

from application.product_guest_identity import (
    PRODUCT_GUEST_COOKIE,
    PRODUCT_GUEST_COOKIE_MAX_AGE_SECONDS,
    ProductGuestIdentity,
    resolve_product_guest_identity,
    set_product_guest_cookie,
)


GUEST_ID = UUID("12345678-1234-4abc-8def-1234567890ab")


def _request(*, cookie=None, scheme="http", forwarded=""):
    headers = {}
    if forwarded:
        headers["x-forwarded-proto"] = forwarded
    cookies = {}
    if cookie is not None:
        cookies[PRODUCT_GUEST_COOKIE] = cookie
    return SimpleNamespace(
        cookies=cookies,
        url=SimpleNamespace(scheme=scheme),
        headers=headers,
    )


def test_missing_guest_cookie_mints_explicit_uuid_without_mutating_response():
    factory = Mock(return_value=GUEST_ID)

    identity = resolve_product_guest_identity(_request(), uuid_factory=factory)

    assert identity == ProductGuestIdentity(GUEST_ID, True)
    factory.assert_called_once_with()


def test_existing_canonical_guest_cookie_is_reused_stably():
    factory = Mock()

    identity = resolve_product_guest_identity(
        _request(cookie=str(GUEST_ID)),
        uuid_factory=factory,
    )

    assert identity == ProductGuestIdentity(GUEST_ID, False)
    factory.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-uuid",
        "{12345678-1234-4abc-8def-1234567890ab}",
        "12345678-1234-4ABC-8DEF-1234567890AB",
    ],
)
def test_invalid_or_noncanonical_guest_cookie_is_replaced(value):
    replacement = UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")

    identity = resolve_product_guest_identity(
        _request(cookie=value),
        uuid_factory=lambda: replacement,
    )

    assert identity == ProductGuestIdentity(replacement, True)


def test_uuid_factory_must_return_uuid():
    with pytest.raises(TypeError, match="must return UUID"):
        resolve_product_guest_identity(_request(), uuid_factory=lambda: "not-uuid")


def test_guest_cookie_is_persistent_host_only_http_only_and_same_site_lax():
    response = JSONResponse({"status": "ok"})
    request = _request()

    with patch(
        "application.product_guest_identity.product_cookie_secure",
        return_value=False,
    ):
        set_product_guest_cookie(response, request, guest_id=GUEST_ID)

    header = response.headers["set-cookie"]
    assert header.startswith(f"{PRODUCT_GUEST_COOKIE}={GUEST_ID};")
    assert f"Max-Age={PRODUCT_GUEST_COOKIE_MAX_AGE_SECONDS}" in header
    assert "HttpOnly" in header
    assert "Path=/" in header
    assert "SameSite=lax" in header
    assert "Domain=" not in header
    assert "Secure" not in header


def test_guest_cookie_reuses_product_secure_cookie_policy():
    response = JSONResponse({"status": "ok"})
    request = _request(scheme="https")

    with patch(
        "application.product_guest_identity.product_cookie_secure",
        return_value=True,
    ) as secure:
        set_product_guest_cookie(response, request, guest_id=GUEST_ID)

    secure.assert_called_once_with(request)
    assert "Secure" in response.headers["set-cookie"]


def test_guest_cookie_setter_rejects_non_uuid_identity():
    with pytest.raises(TypeError, match="must be UUID"):
        set_product_guest_cookie(
            JSONResponse({"status": "ok"}),
            _request(),
            guest_id="12345678-1234-4abc-8def-1234567890ab",
        )
