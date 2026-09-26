from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.application.security.authentication import AuthenticationError
from app.application.security.clock import Clock
from app.application.security.credentials import (
    CredentialRepository,
    PasswordCredential,
)
from app.application.security.passwords import PasswordHasher
from app.application.security.refresh import (
    IssuedRefreshToken,
    RefreshRepository,
    RefreshSessionRecord,
    RefreshTokenRecord,
    RefreshTokenService,
)
from app.application.security.sessions import AuthSessionTokens
from app.application.security.tokens import AccessTokenService, IssuedAccessToken
from app.domain.entities.user import User, UserRole
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.security.sqlalchemy_login_session_service import (
    SQLAlchemyLoginSessionService,
)

FROZEN_NOW = datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)
DUMMY_PHC = "$argon2id$v=19$m=65536,t=3,p=4$dummy$dummy"


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


class FakeCredentialRepository(CredentialRepository):
    def __init__(
        self,
        credential: PasswordCredential | None = None,
        replace_success: bool = True,
        replace_raises: bool = False,
    ) -> None:
        self.credential = credential
        self.replace_success = replace_success
        self.replace_raises = replace_raises
        self.replace_calls: list[tuple[UUID, str, str]] = []

    async def add(self, credential: PasswordCredential) -> None:
        self.credential = credential

    async def get_by_user_id(self, user_id: UUID) -> PasswordCredential | None:
        return (
            self.credential
            if self.credential and self.credential.user_id == user_id
            else None
        )

    async def replace_hash(
        self, user_id: UUID, expected_hash: str, replacement_hash: str
    ) -> bool:
        self.replace_calls.append((user_id, expected_hash, replacement_hash))
        if self.replace_raises:
            raise RuntimeError("Database maintenance connection lost")
        return self.replace_success


class FakeRefreshRepository(RefreshRepository):
    def __init__(self, fail_on_add_token: bool = False) -> None:
        self.sessions: list[RefreshSessionRecord] = []
        self.tokens: list[RefreshTokenRecord] = []
        self.fail_on_add_token = fail_on_add_token

    async def add_session(self, record: RefreshSessionRecord) -> None:
        self.sessions.append(record)

    async def add_token(self, record: RefreshTokenRecord) -> None:
        if self.fail_on_add_token:
            raise RuntimeError("Forced token insertion failure")
        self.tokens.append(record)

    async def find_token_by_hash(
        self, token_hash: bytes
    ) -> RefreshTokenRecord | None:
        for t in self.tokens:
            if t.token_hash == token_hash:
                return t
        return None

    async def lock_session(self, session_id: UUID) -> RefreshSessionRecord | None:
        for s in self.sessions:
            if s.id == session_id:
                return s
        return None

    async def lock_token(self, token_id: UUID) -> RefreshTokenRecord | None:
        for t in self.tokens:
            if t.id == token_id:
                return t
        return None

    async def mark_token_consumed(
        self, token_id: UUID, consumed_at: datetime
    ) -> None:
        pass

    async def revoke_session(self, session_id: UUID, revoked_at: datetime) -> None:
        pass


class FakePasswordHasher(PasswordHasher):
    def __init__(self, needs_rehash_flag: bool = False) -> None:
        self.needs_rehash_flag = needs_rehash_flag

    def hash(self, password: str) -> str:
        return f"hashed_{password}"

    def verify(self, password: str, encoded_hash: str) -> bool:
        if encoded_hash == DUMMY_PHC:
            return False
        return encoded_hash == f"hashed_{password}" or encoded_hash == "old_hash"

    def needs_rehash(self, encoded_hash: str) -> bool:
        return self.needs_rehash_flag


class FakeAccessTokenService(AccessTokenService):
    def issue(self, user: User) -> IssuedAccessToken:
        return IssuedAccessToken(
            raw_token="fake.access.jwt",
            expires_at=FROZEN_NOW + timedelta(seconds=600),
            jti=uuid4(),
        )

    def validate(self, raw_token: str) -> Any:
        pass


class FakeRefreshTokenService(RefreshTokenService):
    def issue(self) -> IssuedRefreshToken:
        return IssuedRefreshToken(
            raw_token="fake_raw_refresh_token_string_43chars_long",
            token_hash=b"digest_sha256_32bytes_length____",
        )

    def digest(self, raw_token: str) -> bytes:
        return b"digest_sha256_32bytes_length____"


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

    async def __aenter__(self) -> "FakeAsyncSession":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
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
async def test_login_successful_creates_durable_session_and_tokens() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
    cred_repo = FakeCredentialRepository(
        PasswordCredential(user_id=user.id, password_hash="hashed_Secret123!")
    )
    refresh_repo = FakeRefreshRepository()
    clock = FrozenClock()
    hasher = FakePasswordHasher()
    access_service = FakeAccessTokenService()
    refresh_service = FakeRefreshTokenService()
    session_factory = FakeSessionFactory()

    service = SQLAlchemyLoginSessionService(
        session_factory=session_factory,
        password_hasher=hasher,
        access_token_service=access_service,
        refresh_token_service=refresh_service,
        clock=clock,
        dummy_password_hash=DUMMY_PHC,
        user_repo=user_repo,
        cred_repo=cred_repo,
        refresh_repo=refresh_repo,
    )

    result = await service.login("richard@example.com", "Secret123!")

    assert isinstance(result, AuthSessionTokens)
    assert result.access_token == "fake.access.jwt"
    assert result.access_expires_at == FROZEN_NOW + timedelta(seconds=600)
    assert result.refresh_token == "fake_raw_refresh_token_string_43chars_long"
    assert result.refresh_expires_at == FROZEN_NOW + timedelta(minutes=30)

    assert len(refresh_repo.sessions) == 1
    assert len(refresh_repo.tokens) == 1

    s1 = refresh_repo.sessions[0]
    r1 = refresh_repo.tokens[0]

    assert s1.user_id == user.id
    assert s1.created_at == FROZEN_NOW
    assert s1.absolute_expires_at == FROZEN_NOW + timedelta(hours=8)
    assert s1.revoked_at is None

    assert r1.session_id == s1.id
    assert r1.parent_token_id is None
    assert r1.token_hash == b"digest_sha256_32bytes_length____"
    assert r1.issued_at == FROZEN_NOW
    assert r1.expires_at == FROZEN_NOW + timedelta(minutes=30)
    assert r1.consumed_at is None


@pytest.mark.asyncio
async def test_login_failed_authentication_creates_no_session_or_tokens() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
    cred_repo = FakeCredentialRepository(
        PasswordCredential(user_id=user.id, password_hash="hashed_Secret123!")
    )
    refresh_repo = FakeRefreshRepository()
    clock = FrozenClock()
    hasher = FakePasswordHasher()

    service = SQLAlchemyLoginSessionService(
        session_factory=FakeSessionFactory(),
        password_hasher=hasher,
        access_token_service=FakeAccessTokenService(),
        refresh_token_service=FakeRefreshTokenService(),
        clock=clock,
        dummy_password_hash=DUMMY_PHC,
        user_repo=user_repo,
        cred_repo=cred_repo,
        refresh_repo=refresh_repo,
    )

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await service.login("richard@example.com", "WrongPassword!")

    assert len(refresh_repo.sessions) == 0
    assert len(refresh_repo.tokens) == 0


@pytest.mark.asyncio
async def test_login_session_b_failure_rolls_back_and_raises_sanitized_error() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
    cred_repo = FakeCredentialRepository(
        PasswordCredential(user_id=user.id, password_hash="hashed_Secret123!")
    )
    refresh_repo = FakeRefreshRepository(fail_on_add_token=True)

    service = SQLAlchemyLoginSessionService(
        session_factory=FakeSessionFactory(),
        password_hasher=FakePasswordHasher(),
        access_token_service=FakeAccessTokenService(),
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(),
        dummy_password_hash=DUMMY_PHC,
        user_repo=user_repo,
        cred_repo=cred_repo,
        refresh_repo=refresh_repo,
    )

    with pytest.raises(RuntimeError, match="session creation failed"):
        await service.login("richard@example.com", "Secret123!")


@pytest.mark.asyncio
async def test_login_post_commit_rehash_failure_does_not_fail_login() -> None:
    user = User.create("richard@example.com", UserRole.ANALYST)
    user_repo = FakeUserRepository(user)
    cred_repo = FakeCredentialRepository(
        PasswordCredential(user_id=user.id, password_hash="old_hash"),
        replace_raises=True,
    )
    refresh_repo = FakeRefreshRepository()
    hasher = FakePasswordHasher(needs_rehash_flag=True)

    service = SQLAlchemyLoginSessionService(
        session_factory=FakeSessionFactory(),
        password_hasher=hasher,
        access_token_service=FakeAccessTokenService(),
        refresh_token_service=FakeRefreshTokenService(),
        clock=FrozenClock(),
        dummy_password_hash=DUMMY_PHC,
        user_repo=user_repo,
        cred_repo=cred_repo,
        refresh_repo=refresh_repo,
    )

    result = await service.login("richard@example.com", "Secret123!")

    assert isinstance(result, AuthSessionTokens)
    assert len(refresh_repo.sessions) == 1
    assert len(cred_repo.replace_calls) == 1
