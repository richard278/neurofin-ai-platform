from datetime import UTC, datetime, timedelta
from typing import Any, Self
from uuid import UUID, uuid4

import pytest

from app.application.security.clock import Clock
from app.application.security.refresh import (
    InvalidRefreshTokenError,
    IssuedRefreshToken,
    RefreshAuthenticationError,
    RefreshRepository,
    RefreshSessionRecord,
    RefreshTokenRecord,
    RefreshTokenService,
)
from app.application.security.sessions import AuthSessionTokens
from app.application.security.tokens import AccessTokenService, IssuedAccessToken
from app.domain.entities.user import User, UserRole
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.security.sqlalchemy_refresh_session_service import (
    SQLAlchemyRefreshSessionService,
)

FROZEN_NOW = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)


class FrozenClock(Clock):
    def __init__(self, now: datetime = FROZEN_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeUserRepository(UserRepository):
    def __init__(self, user: User | None = None) -> None:
        self.user = user

    async def add(self, user: User) -> None:
        self.user = user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.user if self.user and self.user.id == user_id else None

    async def get_by_email(self, email: str) -> User | None:
        return self.user if self.user and self.user.email == email else None


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


class FakeAccessTokenService(AccessTokenService):
    def issue(self, user: User) -> IssuedAccessToken:
        return IssuedAccessToken(
            raw_token="fake.rotated.access.jwt",
            expires_at=FROZEN_NOW + timedelta(seconds=600),
            jti=uuid4(),
        )

    def validate(self, raw_token: str) -> Any:
        pass


class FakeRefreshTokenService(RefreshTokenService):
    def __init__(self, start_counter: int = 1) -> None:
        self.issue_counter = start_counter

    def issue(self) -> IssuedRefreshToken:
        token_str = f"fake_raw_r{self.issue_counter}_refresh_token_43chars"
        digest_val = f"digest_sha256_r{self.issue_counter}________________".encode()[:32]
        self.issue_counter += 1
        return IssuedRefreshToken(raw_token=token_str, token_hash=digest_val)

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
async def test_refresh_malformed_token_raises_generic_error_without_db_lookup() -> None:
    refresh_repo = FakeRefreshRepository()
    service = SQLAlchemyRefreshSessionService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        access_token_service=FakeAccessTokenService(),
        clock=FrozenClock(),
        user_repo=FakeUserRepository(),
        refresh_repo=refresh_repo,
    )

    with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
        await service.refresh("malformed_token")

    assert len(refresh_repo.tokens) == 0


@pytest.mark.asyncio
async def test_refresh_unknown_digest_raises_generic_error() -> None:
    refresh_repo = FakeRefreshRepository()
    service = SQLAlchemyRefreshSessionService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        access_token_service=FakeAccessTokenService(),
        clock=FrozenClock(),
        user_repo=FakeUserRepository(),
        refresh_repo=refresh_repo,
    )

    with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
        await service.refresh("fake_raw_r1_refresh_token_43chars")


@pytest.mark.asyncio
async def test_refresh_valid_rotation_creates_r2_and_consumes_r1() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
    refresh_repo = FakeRefreshRepository()
    clock = FrozenClock(FROZEN_NOW)

    s1_id = uuid4()
    r1_id = uuid4()
    r1_digest = b"digest_sha256_r1________________"

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(minutes=5),
        absolute_expires_at=FROZEN_NOW + timedelta(hours=8),
        revoked_at=None,
    )
    r1_record = RefreshTokenRecord(
        id=r1_id,
        session_id=s1_id,
        parent_token_id=None,
        token_hash=r1_digest,
        issued_at=FROZEN_NOW - timedelta(minutes=5),
        expires_at=FROZEN_NOW + timedelta(minutes=25),
        consumed_at=None,
    )

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)

    refresh_service = FakeRefreshTokenService(start_counter=2)
    service = SQLAlchemyRefreshSessionService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=refresh_service,
        access_token_service=FakeAccessTokenService(),
        clock=clock,
        user_repo=user_repo,
        refresh_repo=refresh_repo,
    )

    tokens = await service.refresh("fake_raw_r1_refresh_token_43chars")

    assert isinstance(tokens, AuthSessionTokens)
    assert tokens.access_token == "fake.rotated.access.jwt"
    assert tokens.refresh_token == "fake_raw_r2_refresh_token_43chars"
    assert tokens.refresh_expires_at == FROZEN_NOW + timedelta(minutes=30)

    # R1 marked consumed
    assert len(refresh_repo.consumed_calls) == 1
    assert refresh_repo.consumed_calls[0] == (r1_id, FROZEN_NOW)

    # R2 created with parent_token_id = R1.id
    r2_digest = b"digest_sha256_r2________________"
    r2_record = refresh_repo.tokens_by_hash.get(r2_digest)
    assert r2_record is not None
    assert r2_record.session_id == s1_id
    assert r2_record.parent_token_id == r1_id
    assert r2_record.consumed_at is None


@pytest.mark.asyncio
async def test_refresh_consumed_after_expiry_precedence_revokes_family_and_commits() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
    refresh_repo = FakeRefreshRepository()

    # Time is FROZEN_NOW. R1 was issued 40 minutes ago, expired 10 minutes ago, AND consumed 35 minutes ago.
    # Absolute session expires in 7 hours.
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
        expires_at=FROZEN_NOW - timedelta(minutes=10),  # EXPIRED!
        consumed_at=FROZEN_NOW - timedelta(minutes=35),  # ALSO CONSUMED!
    )

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)

    session_factory = FakeSessionFactory()
    service = SQLAlchemyRefreshSessionService(
        session_factory=session_factory,
        refresh_token_service=FakeRefreshTokenService(),
        access_token_service=FakeAccessTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        user_repo=user_repo,
        refresh_repo=refresh_repo,
    )

    with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
        await service.refresh("fake_raw_r1_refresh_token_43chars")

    # REUSE precedence: family WAS revoked and transaction WAS committed before raising error!
    assert len(refresh_repo.revoked_calls) == 1
    assert refresh_repo.revoked_calls[0] == (s1_id, FROZEN_NOW)
    assert refresh_repo.sessions[s1_id].revoked_at == FROZEN_NOW

    # Session committed (not rolled back)
    assert any(s.committed for s in session_factory.sessions_created)


@pytest.mark.asyncio
async def test_refresh_revoked_family_rejects_without_mutation() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
    refresh_repo = FakeRefreshRepository()

    s1_id = uuid4()
    r1_id = uuid4()
    r1_digest = b"digest_sha256_r1________________"
    original_revoked_at = FROZEN_NOW - timedelta(minutes=10)

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(hours=1),
        absolute_expires_at=FROZEN_NOW + timedelta(hours=7),
        revoked_at=original_revoked_at,
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

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)

    service = SQLAlchemyRefreshSessionService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        access_token_service=FakeAccessTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        user_repo=user_repo,
        refresh_repo=refresh_repo,
    )

    with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
        await service.refresh("fake_raw_r1_refresh_token_43chars")

    assert len(refresh_repo.consumed_calls) == 0
    assert len(refresh_repo.tokens) == 1
    assert len(refresh_repo.revoked_calls) == 0
    assert refresh_repo.sessions[s1_id].revoked_at == original_revoked_at


@pytest.mark.asyncio
async def test_refresh_absolute_expired_family_rejects_without_rotation() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
    refresh_repo = FakeRefreshRepository()

    s1_id = uuid4()
    r1_id = uuid4()
    r1_digest = b"digest_sha256_r1________________"

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=FROZEN_NOW - timedelta(hours=9),
        absolute_expires_at=FROZEN_NOW - timedelta(minutes=1),  # ABSOLUTE EXPIRED
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

    service = SQLAlchemyRefreshSessionService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        access_token_service=FakeAccessTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        user_repo=user_repo,
        refresh_repo=refresh_repo,
    )

    with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
        await service.refresh("fake_raw_r1_refresh_token_43chars")

    assert len(refresh_repo.consumed_calls) == 0
    assert len(refresh_repo.tokens) == 1
    assert len(refresh_repo.revoked_calls) == 0
    assert refresh_repo.sessions[s1_id].revoked_at is None


@pytest.mark.asyncio
async def test_refresh_unconsumed_expired_token_rejects_without_revoking_family() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
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
        expires_at=FROZEN_NOW - timedelta(minutes=5),  # TOKEN EXPIRED BUT UNCONSUMED
        consumed_at=None,
    )

    await refresh_repo.add_session(s1_record)
    await refresh_repo.add_token(r1_record)

    service = SQLAlchemyRefreshSessionService(
        session_factory=FakeSessionFactory(),
        refresh_token_service=FakeRefreshTokenService(),
        access_token_service=FakeAccessTokenService(),
        clock=FrozenClock(FROZEN_NOW),
        user_repo=user_repo,
        refresh_repo=refresh_repo,
    )

    with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
        await service.refresh("fake_raw_r1_refresh_token_43chars")

    assert len(refresh_repo.revoked_calls) == 0
    assert refresh_repo.sessions[s1_id].revoked_at is None
    assert len(refresh_repo.consumed_calls) == 0
    assert len(refresh_repo.tokens) == 1
