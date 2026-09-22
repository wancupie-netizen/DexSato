"""Provider-neutral contract for passwordless product authentication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class VerifiedProductIdentity:
    auth_provider: str
    auth_subject: str
    email: str


class ProductAuthUnavailableError(RuntimeError):
    """Raised when product authentication is unavailable or misconfigured."""


class ProductAuthDeliveryError(RuntimeError):
    """Raised when an OTP cannot be requested without exposing provider detail."""


class ProductAuthVerificationError(RuntimeError):
    """Raised when an OTP cannot be verified without exposing provider detail."""


class ProductAuthProvider(Protocol):
    def request_email_otp(self, *, email: str) -> None: ...

    def verify_email_otp(
        self,
        *,
        email: str,
        code: str,
    ) -> VerifiedProductIdentity: ...
