from datetime import UTC, datetime, timedelta
from typing import Any, Self
from uuid import UUID, uuid4

import pytest

from app.application.security.clock import Clock
from app.application.security.refresh import (
    InvalidRefreshTokenError,
    RefreshRepository,
    RefreshSessionRecord,
    RefreshTokenRecord,
    RefreshTokenService,
)
from app.domain.entities.user import User, UserRole
from app.infrastructure.security.sqlalchemy_logout_service import (
    SQLAlchemyLogoutService,
)

FROZEN_NOW = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)


class FrozenClock(Clock):
    def __init__(self, now: datetime = FROZEN_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeRefreshRepository(RefreshRepository):
    def __init__(self) -> None:
        self.sessions: dict[UUID, RefreshSessionRecord] = {}
        self.tokens: dict[UUID, RefreshTokenRecord] = {}
        self.tokens_by_hash: dict[bytes, RefreshTokenRecord] = {}
        self.revoked_calls: list[tuple[UUID, datetime]] = []
        self.consumed_calls: list[tuple[UUID, datetime]] = []

    async def add_session(self, record: RefreshSessionRecord) -> None:
        self.sessions[record.id] = record

    async def add_token(self, record: RefreshTokenRecord) -> None:
        self.tokens[record.id] = record
        self.tokens_by_hash[record.token_hash] = record

    async def find_token_by_hash(
        self, token_hash: bytes
    ) -> RefreshTokenRecord | None:
        return self.tokens_by_hash.get(token_hash)

    async def lock_session(self, session_id: UUID) -> RefreshSessionRecord | None:
        return self.sessions.get(session_id)

    async def lock_token(self, token_id: UUID) -> RefreshTokenRecord | None:
        return self.tokens.get(token_id)

    async def mark_token_consumed(
        self, token_id: UUID, consumed_at: datetime
    ) -> None:
        self.consumed_calls.append((token_id, consumed_at))
        tok = self.tokens.get(token_id)
        if tok:
            updated = RefreshTokenRecord(
                id=tok.id,
                session_id=tok.session_id,
                parent_token_id=tok.parent_token_id,
                token_hash=tok.token_hash,
                issued_at=tok.issued_at,
                expires_at=tok.expires_at,
                consumed_at=consumed_at,
            )
            self.tokens[token_id] = updated
            self.tokens_by_hash[tok.token_hash] = updated

    async def revoke_session(self, session_id: UUID, revoked_at: datetime) -> None:
        self.revoked_calls.append((session_id, revoked_at))
        sess = self.sessions.get(session_id)
        if sess:
            updated = RefreshSessionRecord(
                id=sess.id,
                user_id=sess.user_id,
                created_at=sess.created_at,
                absolute_expires_at=sess.absolute_expires_at,
                revoked_at=revoked_at,
            )
            self.sessions[session_id] = updated


class FakeRefreshTokenService(RefreshTokenService):
    def issue(self) -> Any:
        pass

    def digest(self, raw_token: str) -> bytes:
        if raw_token == "malformed_token":
            raise InvalidRefreshTokenError("invalid refresh token")
        if raw_token == "fake_raw_r1_refresh_token_43chars":
            return b"digest_sha256_r1________________"
        if raw_token == "fake_raw_r2_refresh_token_43chars":
            return b"digest_sha256_r2________________"
        return f"digest_sha256_{raw_token[:2]}________________".encode()[:32]


class FakeAsyncSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        await self.close()


class FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions_created: list[FakeAsyncSession] = []

    def __call__(self) -> FakeAsyncSession:
        session = FakeAsyncSession()
        self.sessions_created.append(session)
        return session


@pytest.mark.asyncio
async def test_logout_none_token_succeeds_without_db_lookup_or_mutation() -> None:
    refresh_repo = FakeRefreshRepository()
    session_factory = FakeSessionFactory()
    service = SQLAlchemyLogoutService(
        session_factory=session_factory,
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(),
        refresh_repo=refresh_repo,
    )

    await service.logout(None)

    assert len(session_factory.sessions_created) == 0
    assert len(refresh_repo.revoked_calls) == 0


@pytest.mark.asyncio
async def test_logout_malformed_token_succeeds_without_db_mutation() -> None:
    refresh_repo = FakeRefreshRepository()
    session_factory = FakeSessionFactory()
    service = SQLAlchemyLogoutService(
        session_factory=session_factory,
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(),
        refresh_repo=refresh_repo,
    )

    await service.logout("malformed_token")

    assert len(session_factory.sessions_created) == 0
    assert len(refresh_repo.revoked_calls) == 0


@pytest.mark.asyncio
async def test_logout_unknown_digest_succeeds_without_mutation() -> None:
    refresh_repo = FakeRefreshRepository()
    session_factory = FakeSessionFactory()
    service = SQLAlchemyLogoutService(
        session_factory=session_factory,
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(),
        refresh_repo=refresh_repo,
    )

    await service.logout("fake_raw_r1_refresh_token_43chars")

    assert len(session_factory.sessions_created) == 1
    assert len(refresh_repo.revoked_calls) == 0


@pytest.mark.asyncio
async def test_logout_active_family_revokes_family_and_commits() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    refresh_repo = FakeRefreshRepository()

    s1_id = uuid4()
    r1_id = uuid4()
    r1_digest = b"digest_sha256_r1________________"

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(minutes=10),
        absolute_expires_at=FROZEN_NOW + timedelta(hours=8),
        revoked_at=None,
    )
    r1_record = RefreshTokenRecord(
        id=r1_id,
        session_id=s1_id,
        parent_token_id=None,
        token_hash=r1_digest,
        issued_at=FROZEN_NOW - timedelta(minutes=10),
        expires_at=FROZEN_NOW + timedelta(minutes=20),
        consumed_at=None,
    )

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)

    session_factory = FakeSessionFactory()
    service = SQLAlchemyLogoutService(
        session_factory=session_factory,
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        refresh_repo=refresh_repo,
    )

    await service.logout("fake_raw_r1_refresh_token_43chars")

    assert len(refresh_repo.revoked_calls) == 1
    assert refresh_repo.revoked_calls[0] == (s1_id, FROZEN_NOW)
    assert refresh_repo.sessions[s1_id].revoked_at == FROZEN_NOW
    assert any(s.committed for s in session_factory.sessions_created)


@pytest.mark.asyncio
async def test_logout_already_revoked_family_is_idempotent() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    refresh_repo = FakeRefreshRepository()
    original_revoked_at = FROZEN_NOW - timedelta(minutes=5)

    s1_id = uuid4()
    r1_id = uuid4()
    r1_digest = b"digest_sha256_r1________________"

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(minutes=30),
        absolute_expires_at=FROZEN_NOW + timedelta(hours=7),
        revoked_at=original_revoked_at,
    )
    r1_record = RefreshTokenRecord(
        id=r1_id,
        session_id=s1_id,
        parent_token_id=None,
        token_hash=r1_digest,
        issued_at=FROZEN_NOW - timedelta(minutes=30),
        expires_at=FROZEN_NOW + timedelta(minutes=10),
        consumed_at=None,
    )

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)

    service = SQLAlchemyLogoutService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        refresh_repo=refresh_repo,
    )

    await service.logout("fake_raw_r1_refresh_token_43chars")

    assert len(refresh_repo.revoked_calls) == 0
    assert refresh_repo.sessions[s1_id].revoked_at == original_revoked_at


@pytest.mark.asyncio
async def test_logout_expired_token_in_active_family_revokes_family() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    refresh_repo = FakeRefreshRepository()

    s1_id = uuid4()
    r1_id = uuid4()
    r1_digest = b"digest_sha256_r1________________"

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(minutes=40),
        absolute_expires_at=FROZEN_NOW + timedelta(hours=7),
        revoked_at=None,
    )
    r1_record = RefreshTokenRecord(
        id=r1_id,
        session_id=s1_id,
        parent_token_id=None,
        token_hash=r1_digest,
        issued_at=FROZEN_NOW - timedelta(minutes=40),
        expires_at=FROZEN_NOW - timedelta(minutes=10),  # EXPIRED TOKEN
        consumed_at=None,
    )

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)

    service = SQLAlchemyLogoutService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        refresh_repo=refresh_repo,
    )

    await service.logout("fake_raw_r1_refresh_token_43chars")

    assert len(refresh_repo.revoked_calls) == 1
    assert refresh_repo.sessions[s1_id].revoked_at == FROZEN_NOW


@pytest.mark.asyncio
async def test_logout_consumed_token_in_active_family_revokes_family_silently() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    refresh_repo = FakeRefreshRepository()

    s1_id = uuid4()
    r1_id = uuid4()
    r1_digest = b"digest_sha256_r1________________"

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(minutes=30),
        absolute_expires_at=FROZEN_NOW + timedelta(hours=7),
        revoked_at=None,
    )
    r1_record = RefreshTokenRecord(
        id=r1_id,
        session_id=s1_id,
        parent_token_id=None,
        token_hash=r1_digest,
        issued_at=FROZEN_NOW - timedelta(minutes=30),
        expires_at=FROZEN_NOW + timedelta(minutes=10),
        consumed_at=FROZEN_NOW - timedelta(minutes=5),  # CONSUMED TOKEN
    )

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)

    service = SQLAlchemyLogoutService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        refresh_repo=refresh_repo,
    )

    # Must complete normally (no error raised)
    await service.logout("fake_raw_r1_refresh_token_43chars")

    assert len(refresh_repo.revoked_calls) == 1
    assert refresh_repo.sessions[s1_id].revoked_at == FROZEN_NOW


@pytest.mark.asyncio
async def test_logout_revokes_only_target_family_other_user_sessions_remain_active() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    refresh_repo = FakeRefreshRepository()

    # Session S1 (Laptop)
    s1_id = uuid4()
    r1_id = uuid4()
    r1_digest = b"digest_sha256_r1________________"
    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(hours=1),
        absolute_expires_at=FROZEN_NOW + timedelta(hours=7),
        revoked_at=None,
    )
    r1_record = RefreshTokenRecord(
        id=r1_id,
        session_id=s1_id,
        parent_token_id=None,
        token_hash=r1_digest,
        issued_at=FROZEN_NOW - timedelta(hours=1),
        expires_at=FROZEN_NOW + timedelta(minutes=20),
        consumed_at=None,
    )

    # Session S2 (Mobile)
    s2_id = uuid4()
    r2_id = uuid4()
    r2_digest = b"digest_sha256_r2________________"
    s2_record = RefreshSessionRecord(
        id=s2_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(minutes=10),
        absolute_expires_at=FROZEN_NOW + timedelta(hours=8),
        revoked_at=None,
    )
    r2_record = RefreshTokenRecord(
        id=r2_id,
        session_id=s2_id,
        parent_token_id=None,
        token_hash=r2_digest,
        issued_at=FROZEN_NOW - timedelta(minutes=10),
        expires_at=FROZEN_NOW + timedelta(minutes=20),
        consumed_at=None,
    )

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)
    await refresh_repo.add_session(s2_record)
    await refresh_repo.add_token(r2_record)

    service = SQLAlchemyLogoutService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        refresh_repo=refresh_repo,
    )

    # Logout using S1 token
    await service.logout("fake_raw_r1_refresh_token_43chars")

    assert refresh_repo.sessions[s1_id].revoked_at == FROZEN_NOW
    assert refresh_repo.sessions[s2_id].revoked_at is None
