from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities.user import User, UserRole


class InvalidAccessTokenError(RuntimeError):
    """Raised when an access token is invalid, expired, tampered, or malformed."""



@dataclass(frozen=True)
class IssuedAccessToken:
    raw_token: str
    expires_at: datetime
    jti: UUID


@dataclass(frozen=True)
class AccessPrincipal:
    user_id: UUID
    role: UserRole
    issued_at: datetime
    expires_at: datetime
    jti: UUID


class AccessTokenService(Protocol):
    def issue(self, user: User) -> IssuedAccessToken:
        ...

    def validate(self, raw_token: str) -> AccessPrincipal:
        ...
