"""Supabase email-OTP adapter with no browser/provider-session persistence."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from application.product_auth_provider import (
    ProductAuthDeliveryError,
    ProductAuthUnavailableError,
    ProductAuthVerificationError,
    VerifiedProductIdentity,
)
from application.product_identity_service import normalize_email


_MAXIMUM_OTP_LENGTH = 16


def _required_code(value: str) -> str:
    code = value.strip()
    if not code or len(code) > _MAXIMUM_OTP_LENGTH or not code.isascii() or not code.isdigit():
        raise ProductAuthVerificationError("Unable to verify that code.")
    return code


def _response_user(response: Any) -> Any:
    user = getattr(response, "user", None)
    if user is not None:
        return user
    mapping = getattr(response, "data", None)
    if isinstance(mapping, dict):
        return mapping.get("user")
    if isinstance(response, dict):
        return response.get("user")
    return None


def _user_value(user: Any, name: str) -> Any:
    if isinstance(user, dict):
        return user.get(name)
    return getattr(user, name, None)


class SupabaseProductAuthProvider:
    """Use a fresh low-privilege client for every OTP operation."""

    def __init__(self, client_factory: Callable[[], Any]) -> None:
        if not callable(client_factory):
            raise TypeError("client_factory must be callable")
        self._client_factory = client_factory

    def _client(self) -> Any:
        try:
            client = self._client_factory()
        except Exception as error:
            raise ProductAuthUnavailableError("Product authentication is unavailable.") from error
        if client is None or getattr(client, "auth", None) is None:
            raise ProductAuthUnavailableError("Product authentication is unavailable.")
        return client

    def request_email_otp(self, *, email: str) -> None:
        normalized = normalize_email(email)
        try:
            self._client().auth.sign_in_with_otp(
                {
                    "email": normalized,
                    "options": {"should_create_user": True},
                }
            )
        except Exception as error:
            raise ProductAuthDeliveryError("Unable to send a sign-in code.") from error

    def verify_email_otp(
        self,
        *,
        email: str,
        code: str,
    ) -> VerifiedProductIdentity:
        normalized = normalize_email(email)
        token = _required_code(code)
        try:
            response = self._client().auth.verify_otp(
                {
                    "email": normalized,
                    "token": token,
                    "type": "email",
                }
            )
        except Exception as error:
            raise ProductAuthVerificationError("Unable to verify that code.") from error

        user = _response_user(response)
        subject = str(_user_value(user, "id") or "").strip()
        verified_email = normalize_email(str(_user_value(user, "email") or normalized))
        if not subject or len(subject) > 255 or verified_email != normalized:
            raise ProductAuthVerificationError("Unable to verify that code.")
        return VerifiedProductIdentity(
            auth_provider="supabase",
            auth_subject=subject,
            email=verified_email,
        )
