from datetime import timedelta
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.security.authentication import (
    AuthenticateCommand,
    AuthenticateUser,
    AuthenticationError,
)
from app.application.security.clock import Clock
from app.application.security.credentials import CredentialRepository
from app.application.security.passwords import PasswordHasher
from app.application.security.refresh import (
    RefreshRepository,
    RefreshSessionRecord,
    RefreshTokenRecord,
    RefreshTokenService,
)
from app.application.security.sessions import AuthSessionTokens, LoginSessionService
from app.application.security.tokens import AccessTokenService
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.repositories.sqlalchemy_credential_repository import (
    SQLAlchemyCredentialRepository,
)
from app.infrastructure.repositories.sqlalchemy_refresh_repository import (
    SQLAlchemyRefreshRepository,
)
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)

_ABSOLUTE_SESSION_TTL = timedelta(hours=8)
_INITIAL_TOKEN_TTL = timedelta(minutes=30)


class SQLAlchemyLoginSessionService(LoginSessionService):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | Callable[[], Any],
        password_hasher: PasswordHasher,
        access_token_service: AccessTokenService,
        refresh_token_service: RefreshTokenService,
        clock: Clock,
        dummy_password_hash: str,
        user_repo: type | None = None,
        cred_repo: type | None = None,
        refresh_repo: type | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._password_hasher = password_hasher
        self._access_token_service = access_token_service
        self._refresh_token_service = refresh_token_service
        self._clock = clock
        self._dummy_password_hash = dummy_password_hash
        self._user_repo_cls = user_repo or SQLAlchemyUserRepository
        self._cred_repo_cls = cred_repo or SQLAlchemyCredentialRepository
        self._refresh_repo_cls = refresh_repo or SQLAlchemyRefreshRepository

    async def login(self, email: str, password: str) -> AuthSessionTokens:
        # SESSION A: Authenticate User
        async with self._session_factory() as session_a:
            user_repo = (
                self._user_repo_cls
                if not isinstance(self._user_repo_cls, type)
                else self._user_repo_cls(session_a)
            )
            cred_repo = (
                self._cred_repo_cls
                if not isinstance(self._cred_repo_cls, type)
                else self._cred_repo_cls(session_a)
            )

            auth_use_case = AuthenticateUser(
                user_repository=user_repo,
                credential_repository=cred_repo,
                password_hasher=self._password_hasher,
                dummy_password_hash=self._dummy_password_hash,
            )

            auth_result = await auth_use_case.execute(
                AuthenticateCommand(email=email, password=password)
            )

        # Generate Identifiers & Tokens
        now = self._clock.now()
        s1_id = uuid4()
        r1_id = uuid4()

        issued_refresh = self._refresh_token_service.issue()
        issued_access = self._access_token_service.issue(auth_result.user)

        absolute_expires_at = now + _ABSOLUTE_SESSION_TTL
        refresh_expires_at = min(now + _INITIAL_TOKEN_TTL, absolute_expires_at)

        s1_record = RefreshSessionRecord(
            id=s1_id,
            user_id=auth_result.user.id,
            created_at=now,
            absolute_expires_at=absolute_expires_at,
            revoked_at=None,
        )

        r1_record = RefreshTokenRecord(
            id=r1_id,
            session_id=s1_id,
            parent_token_id=None,
            token_hash=issued_refresh.token_hash,
            issued_at=now,
            expires_at=refresh_expires_at,
            consumed_at=None,
        )

        # SESSION B: Core Session Persistence & Commit
        try:
            async with self._session_factory() as session_b:
                refresh_repo = (
                    self._refresh_repo_cls
                    if not isinstance(self._refresh_repo_cls, type)
                    else self._refresh_repo_cls(session_b)
                )

                await refresh_repo.add_session(s1_record)
                await refresh_repo.add_token(r1_record)
                if hasattr(session_b, "commit"):
                    await session_b.commit()
        except Exception as exc:
            raise RuntimeError("session creation failed") from exc

        # SESSION C: Opportunistic Rehash Maintenance
        if auth_result.rehash is not None:
            try:
                async with self._session_factory() as session_c:
                    cred_repo_c = (
                        self._cred_repo_cls
                        if not isinstance(self._cred_repo_cls, type)
                        else self._cred_repo_cls(session_c)
                    )
                    await cred_repo_c.replace_hash(
                        user_id=auth_result.rehash.user_id,
                        expected_hash=auth_result.rehash.expected_hash,
                        replacement_hash=auth_result.rehash.replacement_hash,
                    )
                    if hasattr(session_c, "commit"):
                        await session_c.commit()
            except Exception:
                pass  # Maintenance failure does not fail login

        return AuthSessionTokens(
            access_token=issued_access.raw_token,
            access_expires_at=issued_access.expires_at,
            refresh_token=issued_refresh.raw_token,
            refresh_expires_at=refresh_expires_at,
        )
