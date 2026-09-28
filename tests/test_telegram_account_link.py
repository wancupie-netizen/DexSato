"""A04D-01 domain behavior without network or production database."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from application.telegram_account_link import TelegramLinkService


class FakeLinks:
    def __init__(self):
        self.requests = {}
        self.links = {}

    def create_request(self, *, user_id, token_hash, created_at, expires_at):
        self.requests[token_hash] = (user_id, created_at, expires_at)

    def redeem_request(self, *, token_hash, telegram_user_id, chat_id):
        import datetime as dt
        row = self.requests.get(token_hash)
        if row is None or row[2] <= dt.datetime.now(UTC):
            return False
        if row[0] in self.links or telegram_user_id in self.links.values():
            return False
        self.links[row[0]] = telegram_user_id
        del self.requests[token_hash]
        return True


def test_token_is_opaque_short_lived_and_single_use():
    repo = FakeLinks()
    service = TelegramLinkService(repo)
    user = uuid4()
    token = service.issue(user_id=user)
    assert len(token) == 43
    assert token not in repo.requests
    (_, issued_at, expires_at), = repo.requests.values()
    assert expires_at - issued_at == timedelta(minutes=10)
    assert service.redeem(token=token, telegram_user_id=123, chat_id=123)
    assert not service.redeem(token=token, telegram_user_id=123, chat_id=123)


def test_private_chat_and_unique_identity_required():
    repo = FakeLinks()
    service = TelegramLinkService(repo)
    first = service.issue(user_id=uuid4())
    assert not service.redeem(token=first, telegram_user_id=1, chat_id=-1)
    assert not service.redeem(token=first, telegram_user_id=1, chat_id=2)
    assert not service.redeem(token=first, telegram_user_id=True, chat_id=1)
    assert service.redeem(token=first, telegram_user_id=1, chat_id=1)
    second = service.issue(user_id=uuid4())
    assert not service.redeem(token=second, telegram_user_id=1, chat_id=1)


def test_malformed_token_does_not_reach_repository():
    repo = FakeLinks()
    service = TelegramLinkService(repo)
    assert not service.redeem(token="/start secret", telegram_user_id=1, chat_id=1)
    assert repo.links == {}


def test_naive_issue_time_is_rejected():
    import pytest
    service = TelegramLinkService(FakeLinks())
    with pytest.raises(ValueError):
        service.issue(user_id=uuid4(), now=datetime(2026, 9, 28))
