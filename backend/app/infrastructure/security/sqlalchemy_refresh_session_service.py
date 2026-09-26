from collections.abc import Callable
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.security.clock import Clock
from app.application.security.refresh import (
    InvalidRefreshTokenError,
    RefreshAuthenticationError,
    RefreshTokenRecord,
    RefreshTokenService,
)
from app.application.security.sessions import AuthSessionTokens, RefreshSessionService
from app.application.security.tokens import AccessTokenService
from app.infrastructure.repositories.sqlalchemy_refresh_repository import (
    SQLAlchemyRefreshRepository,
)
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)

_INITIAL_TOKEN_TTL = timedelta(minutes=30)


class SQLAlchemyRefreshSessionService(RefreshSessionService):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | Callable[[], Any],
        refresh_token_service: RefreshTokenService,
        access_token_service: AccessTokenService,
        clock: Clock,
        user_repo: type | None = None,
        refresh_repo: type | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._refresh_token_service = refresh_token_service
        self._access_token_service = access_token_service
        self._clock = clock
        self._user_repo_cls = user_repo or SQLAlchemyUserRepository
        self._refresh_repo_cls = refresh_repo or SQLAlchemyRefreshRepository

    async def refresh(self, raw_refresh_token: str) -> AuthSessionTokens:
        # Stage 1 — Strict Digest Before DB Mutation
        try:
            digest = self._refresh_token_service.digest(raw_refresh_token)
        except (InvalidRefreshTokenError, ValueError, TypeError) as exc:
            raise RefreshAuthenticationError("refresh authentication failed") from exc

        # SESSION A — Read-Only Pre-Read (Advisory)
        async with self._session_factory() as session_a:
            refresh_repo_a = (
                self._refresh_repo_cls
                if not isinstance(self._refresh_repo_cls, type)
                else self._refresh_repo_cls(session_a)
            )
            token_advisory = await refresh_repo_a.find_token_by_hash(digest)
            if token_advisory is None:
                raise RefreshAuthenticationError("refresh authentication failed")

            token_id = token_advisory.id
            session_id = token_advisory.session_id

        # SESSION B — Authoritative Locked State & Transaction
        is_reuse_detected = False

        async with self._session_factory() as session_b:
            refresh_repo_b = (
                self._refresh_repo_cls
                if not isinstance(self._refresh_repo_cls, type)
                else self._refresh_repo_cls(session_b)
            )
            user_repo_b = (
                self._user_repo_cls
                if not isinstance(self._user_repo_cls, type)
                else self._user_repo_cls(session_b)
            )

            # MANDATORY LOCK ORDER: 1. Session, 2. Token
            session_record = await refresh_repo_b.lock_session(session_id)
            token_record = await refresh_repo_b.lock_token(token_id)

            now = self._clock.now()

            # Decision Order Contract:
            # 1. Session Revoked
            if session_record is None or session_record.revoked_at is not None:
                raise RefreshAuthenticationError("refresh authentication failed")

            # 2. Absolute Session Expiry
            if now >= session_record.absolute_expires_at:
                raise RefreshAuthenticationError("refresh authentication failed")

            # 3. Consumed Token = REUSE (Precedence over Token Expiry!)
            if token_record is None or token_record.consumed_at is not None:
                await refresh_repo_b.revoke_session(session_record.id, now)
                if hasattr(session_b, "commit"):
                    await session_b.commit()
                is_reuse_detected = True

            if not is_reuse_detected:
                # 4. Token Expiry
                if now >= token_record.expires_at:
                    raise RefreshAuthenticationError("refresh authentication failed")

                # 5. Valid Rotation
                user = await user_repo_b.get_by_id(session_record.user_id)
                if user is None:
                    raise RefreshAuthenticationError("refresh authentication failed")

                issued_refresh = self._refresh_token_service.issue()
                issued_access = self._access_token_service.issue(user)

                r2_expires_at = min(
                    now + _INITIAL_TOKEN_TTL,
                    session_record.absolute_expires_at,
                )

                r2_record = RefreshTokenRecord(
                    id=uuid4(),
                    session_id=session_record.id,
                    parent_token_id=token_record.id,
                    token_hash=issued_refresh.token_hash,
                    issued_at=now,
                    expires_at=r2_expires_at,
                    consumed_at=None,
                )

                await refresh_repo_b.mark_token_consumed(token_record.id, now)
                await refresh_repo_b.add_token(r2_record)

                if hasattr(session_b, "commit"):
                    await session_b.commit()

                return AuthSessionTokens(
                    access_token=issued_access.raw_token,
                    access_expires_at=issued_access.expires_at,
                    refresh_token=issued_refresh.raw_token,
                    refresh_expires_at=r2_expires_at,
                )

        # Handle REUSE rejection OUTSIDE transaction block
        if is_reuse_detected:
            raise RefreshAuthenticationError("refresh authentication failed")

        raise RefreshAuthenticationError("refresh authentication failed")
