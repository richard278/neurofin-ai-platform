from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


class InvalidRefreshTokenError(ValueError):
    pass


class RefreshAuthenticationError(RuntimeError):
    pass


class RefreshRepositoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class IssuedRefreshToken:
    raw_token: str
    token_hash: bytes


@dataclass(frozen=True)
class RefreshSessionRecord:
    id: UUID
    user_id: UUID
    created_at: datetime
    absolute_expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class RefreshTokenRecord:
    id: UUID
    session_id: UUID
    parent_token_id: UUID | None
    token_hash: bytes
    issued_at: datetime
    expires_at: datetime
    consumed_at: datetime | None


class RefreshTokenService(Protocol):
    def issue(self) -> IssuedRefreshToken:
        ...

    def digest(self, raw_token: str) -> bytes:
        ...


class RefreshRepository(Protocol):
    async def add_session(self, record: RefreshSessionRecord) -> None:
        ...

    async def add_token(self, record: RefreshTokenRecord) -> None:
        ...

    async def find_token_by_hash(
        self,
        token_hash: bytes,
    ) -> RefreshTokenRecord | None:
        ...

    async def lock_session(
        self,
        session_id: UUID,
    ) -> RefreshSessionRecord | None:
        ...

    async def lock_token(
        self,
        token_id: UUID,
    ) -> RefreshTokenRecord | None:
        ...

    async def mark_token_consumed(
        self,
        token_id: UUID,
        consumed_at: datetime,
    ) -> None:
        ...

    async def revoke_session(
        self,
        session_id: UUID,
        revoked_at: datetime,
    ) -> None:
        ...