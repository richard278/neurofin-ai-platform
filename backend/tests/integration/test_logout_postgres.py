import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.security.clock import Clock
from app.application.security.refresh import (
    RefreshAuthenticationError,
    RefreshSessionRecord,
    RefreshTokenRecord,
)
from app.application.security.tokens import InvalidAccessTokenError
from app.domain.entities.user import User, UserRole
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.infrastructure.security.jwt_access_token_service import (
    JWTAccessTokenService,
)
from app.infrastructure.security.refresh_token_service import (
    SecureRefreshTokenService,
)
from app.infrastructure.security.sqlalchemy_logout_service import (
    SQLAlchemyLogoutService,
)
from app.infrastructure.security.sqlalchemy_refresh_session_service import (
    SQLAlchemyRefreshSessionService,
)

pytestmark = pytest.mark.postgres_integration

RUN_POSTGRES = os.getenv("NEUROFIN_RUN_POSTGRES_INTEGRATION") == "1"
DEFAULT_PG_URL = (
    "postgresql+asyncpg://neurofin_nf_auth_02:neurofin_nf_auth_02_local"
    "@127.0.0.1:55432/neurofin_nf_auth_02"
)
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_PG_URL)


class MutableClock(Clock):
    def __init__(self, initial_now: datetime) -> None:
        self._now = initial_now

    def now(self) -> datetime:
        return self._now

    def advance(self, duration: timedelta) -> None:
        self._now = self._now + duration


def generate_rsa_keys() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv_pem, pub_pem


def _run_alembic(command: str, revision: str = "head") -> None:
    import subprocess
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parents[2]
    cmd = [sys.executable, "-m", "alembic", command, revision]
    env = os.environ.copy()
    env["DATABASE_URL"] = DATABASE_URL
    res = subprocess.run(
        cmd, cwd=backend_dir, env=env, capture_output=True, text=True, check=False
    )
    if res.returncode != 0:
        raise RuntimeError(f"Alembic command failed: {res.stderr}")


async def _clean_db(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await session.execute(
            text("TRUNCATE refresh_tokens, refresh_sessions, user_credentials, users CASCADE")
        )
        await session.commit()


@pytest.mark.asyncio
async def test_logout_postgres_race_condition_refresh_vs_logout() -> None:
    if not RUN_POSTGRES:
        pytest.skip("NEUROFIN_RUN_POSTGRES_INTEGRATION != '1'")

    _run_alembic("upgrade", "head")

    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    await _clean_db(factory)

    start_time = datetime(2026, 9, 26, 12, 0, 0, tzinfo=UTC)
    clock = MutableClock(start_time)
    priv_pem, pub_pem = generate_rsa_keys()

    # Insert user in PostgreSQL
    user = User.create("logout.race@example.com", UserRole.ANALYST)
    async with factory() as session:
        user_repo = SQLAlchemyUserRepository(session)
        await user_repo.add(user)
        await session.commit()

    # Create session S1 and token R1
    refresh_token_svc = SecureRefreshTokenService()
    issued_r1 = refresh_token_svc.issue()
    s1_id = uuid4()
    r1_id = uuid4()

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=start_time,
        absolute_expires_at=start_time + timedelta(hours=8),
        revoked_at=None,
    )
    r1_record = RefreshTokenRecord(
        id=r1_id,
        session_id=s1_id,
        parent_token_id=None,
        token_hash=issued_r1.token_hash,
        issued_at=start_time,
        expires_at=start_time + timedelta(minutes=30),
        consumed_at=None,
    )

    async with factory() as session:
        from app.infrastructure.repositories.sqlalchemy_refresh_repository import (
            SQLAlchemyRefreshRepository,
        )

        refresh_repo = SQLAlchemyRefreshRepository(session)
        await refresh_repo.add_session(s1_record)
        await refresh_repo.add_token(r1_record)
        await session.commit()

    access_token_svc = JWTAccessTokenService(
        private_key_pem=priv_pem,
        public_key_pem=pub_pem,
        clock=clock,
    )

    refresh_service = SQLAlchemyRefreshSessionService(
        session_factory=factory,
        refresh_token_service=refresh_token_svc,
        access_token_service=access_token_svc,
        clock=clock,
    )

    logout_service = SQLAlchemyLogoutService(
        session_factory=factory,
        refresh_token_service=refresh_token_svc,
        clock=clock,
    )

    # Synchronize race launch with barrier
    start_barrier = asyncio.Event()

    async def task_refresh() -> Any:
        await start_barrier.wait()
        try:
            return await refresh_service.refresh(issued_r1.raw_token)
        except Exception as exc:  # noqa: BLE001
            return exc

    async def task_logout() -> Any:
        await start_barrier.wait()
        try:
            return await logout_service.logout(issued_r1.raw_token)
        except Exception as exc:  # noqa: BLE001
            return exc

    t_ref = asyncio.create_task(task_refresh())
    t_log = asyncio.create_task(task_logout())

    # Release barrier simultaneously
    start_barrier.set()
    ref_res, _log_res = await asyncio.gather(t_ref, t_log)

    # Inspect final session state in PostgreSQL
    async with factory() as session:
        sess_row = await session.execute(
            text("SELECT revoked_at FROM refresh_sessions WHERE id = :sid"),
            {"sid": s1_id},
        )
        revoked_at = sess_row.scalar_one_or_none()

    # INVARIANT 1: Family MUST be revoked in PostgreSQL regardless of execution order
    assert revoked_at is not None, "PostgreSQL refresh_session.revoked_at MUST NOT be NULL"

    # INVARIANT 2: No usable successor exists after race
    if not isinstance(ref_res, Exception):
        # Refresh returned R2 tokens
        r2_raw = ref_res.refresh_token
        with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
            await refresh_service.refresh(r2_raw)

    await engine.dispose()


@pytest.mark.asyncio
async def test_logout_postgres_access_jwt_valid_without_denylist() -> None:
    if not RUN_POSTGRES:
        pytest.skip("NEUROFIN_RUN_POSTGRES_INTEGRATION != '1'")

    _run_alembic("upgrade", "head")

    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    await _clean_db(factory)

    start_time = datetime.now(UTC)
    clock = MutableClock(start_time)
    priv_pem, pub_pem = generate_rsa_keys()

    user = User.create("jwt.nodenylist@example.com", UserRole.ANALYST)
    async with factory() as session:
        user_repo = SQLAlchemyUserRepository(session)
        await user_repo.add(user)
        await session.commit()

    access_svc = JWTAccessTokenService(
        private_key_pem=priv_pem,
        public_key_pem=pub_pem,
        clock=clock,
    )
    refresh_svc = SecureRefreshTokenService()

    issued_access = access_svc.issue(user)
    issued_refresh = refresh_svc.issue()
    s1_id = uuid4()

    s1_record = RefreshSessionRecord(
        id=s1_id,
        user_id=user.id,
        created_at=start_time,
        absolute_expires_at=start_time + timedelta(hours=8),
        revoked_at=None,
    )
    r1_record = RefreshTokenRecord(
        id=uuid4(),
        session_id=s1_id,
        parent_token_id=None,
        token_hash=issued_refresh.token_hash,
        issued_at=start_time,
        expires_at=start_time + timedelta(minutes=30),
        consumed_at=None,
    )

    async with factory() as session:
        from app.infrastructure.repositories.sqlalchemy_refresh_repository import (
            SQLAlchemyRefreshRepository,
        )

        refresh_repo = SQLAlchemyRefreshRepository(session)
        await refresh_repo.add_session(s1_record)
        await refresh_repo.add_token(r1_record)
        await session.commit()

    # 1. Access JWT is valid before logout
    principal_before = access_svc.validate(issued_access.raw_token)
    assert principal_before.user_id == user.id

    # 2. Perform logout
    logout_svc = SQLAlchemyLogoutService(
        session_factory=factory,
        refresh_token_service=refresh_svc,
        clock=clock,
    )
    await logout_svc.logout(issued_refresh.raw_token)

    # Verify session is revoked in PostgreSQL
    async with factory() as session:
        sess_row = await session.execute(
            text("SELECT revoked_at FROM refresh_sessions WHERE id = :sid"),
            {"sid": s1_id},
        )
        assert sess_row.scalar_one_or_none() is not None

    # 3. Access JWT STILL VALID immediately after logout (proving NO denylist or per-request DB lookup)
    principal_after_logout = access_svc.validate(issued_access.raw_token)
    assert principal_after_logout.user_id == user.id

    # 4. Issue a token with a clock in the past so its exp < current time
    past_clock = MutableClock(datetime.now(UTC) - timedelta(minutes=15))
    expired_access_svc = JWTAccessTokenService(
        private_key_pem=priv_pem,
        public_key_pem=pub_pem,
        clock=past_clock,
    )
    expired_jwt = expired_access_svc.issue(user)

    # 5. Access JWT fails due to TEMPORAL EXPIRATION, not denylist
    with pytest.raises(InvalidAccessTokenError, match="token validation failed"):
        access_svc.validate(expired_jwt.raw_token)

    await engine.dispose()
