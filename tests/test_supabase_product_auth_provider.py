from types import SimpleNamespace

import pytest

from application.product_auth_provider import ProductAuthVerificationError
from application.supabase_product_auth_provider import SupabaseProductAuthProvider


class FakeAuth:
    def __init__(self):
        self.request = None
        self.verify = None

    def sign_in_with_otp(self, payload):
        self.request = payload
        return SimpleNamespace(user=None, session=None)

    def verify_otp(self, payload):
        self.verify = payload
        return SimpleNamespace(
            user=SimpleNamespace(id="provider-user-1", email="user@example.com"),
            session=SimpleNamespace(access_token="not-returned", refresh_token="not-returned"),
        )


def test_requests_email_otp_with_explicit_account_creation_and_fresh_client():
    clients = []

    def factory():
        client = SimpleNamespace(auth=FakeAuth())
        clients.append(client)
        return client

    provider = SupabaseProductAuthProvider(factory)
    provider.request_email_otp(email=" User@Example.com ")

    assert clients[0].auth.request == {
        "email": "user@example.com",
        "options": {"should_create_user": True},
    }


def test_verifies_email_code_without_returning_provider_session_tokens():
    auth = FakeAuth()
    provider = SupabaseProductAuthProvider(lambda: SimpleNamespace(auth=auth))

    identity = provider.verify_email_otp(email="user@example.com", code="123456")

    assert auth.verify == {
        "email": "user@example.com",
        "token": "123456",
        "type": "email",
    }
    assert identity.auth_provider == "supabase"
    assert identity.auth_subject == "provider-user-1"
    assert identity.email == "user@example.com"
    assert not hasattr(identity, "access_token")
    assert not hasattr(identity, "refresh_token")


@pytest.mark.parametrize("code", ["", "123 456", "abcdef", "1" * 17])
def test_rejects_invalid_code_shape_before_provider_call(code):
    auth = FakeAuth()
    provider = SupabaseProductAuthProvider(lambda: SimpleNamespace(auth=auth))
    with pytest.raises(ProductAuthVerificationError):
        provider.verify_email_otp(email="user@example.com", code=code)
    assert auth.verify is None


def test_rejects_provider_identity_email_mismatch():
    auth = FakeAuth()
    auth.verify_otp = lambda payload: SimpleNamespace(
        user=SimpleNamespace(id="provider-user-1", email="other@example.com")
    )
    provider = SupabaseProductAuthProvider(lambda: SimpleNamespace(auth=auth))
    with pytest.raises(ProductAuthVerificationError):
        provider.verify_email_otp(email="user@example.com", code="123456")
