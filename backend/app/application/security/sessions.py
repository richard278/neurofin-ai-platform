from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AuthSessionTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


class LoginSessionService(Protocol):
    async def login(self, email: str, password: str) -> AuthSessionTokens:
        ...


class RefreshSessionService(Protocol):
    async def refresh(self, raw_refresh_token: str) -> AuthSessionTokens:
        ...


class LogoutService(Protocol):
    async def logout(self, raw_refresh_token: str | None) -> None:
        ...
