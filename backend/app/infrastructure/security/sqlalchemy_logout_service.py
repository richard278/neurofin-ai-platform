from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.security.clock import Clock
from app.application.security.refresh import (
    InvalidRefreshTokenError,
    RefreshTokenService,
)
from app.application.security.sessions import LogoutService
from app.infrastructure.repositories.sqlalchemy_refresh_repository import (
    SQLAlchemyRefreshRepository,
)


class SQLAlchemyLogoutService(LogoutService):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | Callable[[], Any],
        refresh_token_service: RefreshTokenService,
        clock: Clock,
        refresh_repo: type | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._refresh_token_service = refresh_token_service
        self._clock = clock
        self._refresh_repo_cls = refresh_repo or SQLAlchemyRefreshRepository

    async def logout(self, raw_refresh_token: str | None) -> None:
        if raw_refresh_token is None:
            return

        # Stage 1 — Digest validation
        try:
            digest = self._refresh_token_service.digest(raw_refresh_token)
        except (InvalidRefreshTokenError, ValueError, TypeError):
            return

        # SESSION A — Read-Only Pre-Read (Advisory)
        async with self._session_factory() as session_a:
            refresh_repo_a = (
                self._refresh_repo_cls
                if not isinstance(self._refresh_repo_cls, type)
                else self._refresh_repo_cls(session_a)
            )
            token_advisory = await refresh_repo_a.find_token_by_hash(digest)
            if token_advisory is None:
                return

            token_id = token_advisory.id
            session_id = token_advisory.session_id

        # SESSION B — Authoritative Locked State & Transaction
        async with self._session_factory() as session_b:
            refresh_repo_b = (
                self._refresh_repo_cls
                if not isinstance(self._refresh_repo_cls, type)
                else self._refresh_repo_cls(session_b)
            )

            # MANDATORY LOCK ORDER: 1. Session, 2. Token
            session_record = await refresh_repo_b.lock_session(session_id)
            token_record = await refresh_repo_b.lock_token(token_id)

            now = self._clock.now()

            if (
                session_record is not None
                and token_record is not None
                and session_record.revoked_at is None
            ):
                await refresh_repo_b.revoke_session(session_record.id, now)
                if hasattr(session_b, "commit"):
                    await session_b.commit()
