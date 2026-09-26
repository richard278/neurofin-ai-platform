import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import text

from app.application.security.refresh import (
    RefreshAuthenticationError,
    RefreshRepositoryError,
    RefreshSessionRecord,
    RefreshTokenRecord,
)
from app.application.security.sessions import AuthSessionTokens
from app.core.config import get_settings
from app.domain.entities.user import User, UserRole
from app.infrastructure.database.engine import create_database_engine
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.repositories.sqlalchemy_refresh_repository import (
    SQLAlchemyRefreshRepository,
)
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.infrastructure.security.jwt_access_token_service import (
    JWTAccessTokenService,
)
from app.infrastructure.security.refresh_token_service import (
    SecureRefreshTokenService,
)
from app.infrastructure.security.sqlalchemy_refresh_session_service import (
    SQLAlchemyRefreshSessionService,
)
from app.infrastructure.security.system_clock import SystemClock

RUN_INTEGRATION = os.environ.get("NEUROFIN_RUN_POSTGRES_INTEGRATION") == "1"

pytestmark = [
    pytest.mark.postgres_integration,
    pytest.mark.skipif(
        not RUN_INTEGRATION,
        reason="NEUROFIN_RUN_POSTGRES_INTEGRATION != '1'.",
    ),
]

BACKEND_DIR = Path(__file__).parents[2]


def _run_alembic(*args: str) -> None:
    env = os.environ.copy()
    db_url = env.get("DATABASE_URL")
    if not db_url:
        try:
            settings = get_settings()
            if settings.database_url:
                db_url = str(settings.database_url)
        except (AttributeError, KeyError, RuntimeError):
            pass
    if not db_url:
        db_url = "postgresql+asyncpg://neurofin_nf_auth_02:neurofin_nf_auth_02_local@127.0.0.1:55432/neurofin_nf_auth_02"
    env["DATABASE_URL"] = db_url
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
    )


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


class FrozenTestClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


@pytest.mark.asyncio
async def test_refresh_rotation_postgres_same_r1_true_concurrency_and_family_revocation() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    clock = SystemClock()
    priv_pem, pub_pem = generate_rsa_keys()
    access_service = JWTAccessTokenService(priv_pem, pub_pem, clock)
    refresh_service = SecureRefreshTokenService()

    email = f"concurrency_{uuid4().hex[:8]}@example.com"
    user_id = None
    s1_id = uuid4()
    r1_id = uuid4()

    issued_r1 = refresh_service.issue()
    raw_r1 = issued_r1.raw_token
    now = clock.now()

    try:
        # Setup user, session S1, and unconsumed token R1 in PostgreSQL 18.4
        async with factory() as setup_session:
            user_repo = SQLAlchemyUserRepository(setup_session)
            refresh_repo = SQLAlchemyRefreshRepository(setup_session)

            user = User.create(email, UserRole.ANALYST)
            user_id = user.id
            await user_repo.add(user)

            s1_record = RefreshSessionRecord(
                id=s1_id,
                user_id=user.id,
                created_at=now,
                absolute_expires_at=now + timedelta(hours=8),
                revoked_at=None,
            )
            r1_record = RefreshTokenRecord(
                id=r1_id,
                session_id=s1_id,
                parent_token_id=None,
                token_hash=issued_r1.token_hash,
                issued_at=now,
                expires_at=now + timedelta(minutes=30),
                consumed_at=None,
            )

            await refresh_repo.add_session(s1_record)
            await refresh_repo.add_token(r1_record)
            await setup_session.commit()

        # Concurrent Execution Setup
        barrier = asyncio.Event()

        async def worker_refresh() -> tuple[AuthSessionTokens | None, Exception | None]:
            await barrier.wait()
            service = SQLAlchemyRefreshSessionService(
                session_factory=factory,
                refresh_token_service=refresh_service,
                access_token_service=access_service,
                clock=clock,
            )
            try:
                tokens = await service.refresh(raw_r1)
                return tokens, None
            except (RefreshAuthenticationError, RuntimeError) as exc:
                return None, exc

        task_a = asyncio.create_task(worker_refresh())
        task_b = asyncio.create_task(worker_refresh())

        # Release barrier so both workers run concurrently
        barrier.set()

        res_a, res_b = await asyncio.gather(task_a, task_b)

        # Classify outcomes
        success_tokens = [res[0] for res in (res_a, res_b) if res[0] is not None]
        error_exceptions = [res[1] for res in (res_a, res_b) if res[1] is not None]

        # Assertions on concurrency outcomes:
        # Exactly 1 request succeeds, 1 request fails with REUSE / RefreshAuthenticationError
        assert len(success_tokens) == 1
        assert len(error_exceptions) == 1
        assert isinstance(error_exceptions[0], RefreshAuthenticationError)

        r2_raw = success_tokens[0].refresh_token

        # Query PostgreSQL state after concurrency test
        async with factory() as check_session:
            # R1 consumed_at IS NOT NULL
            r1_check = await check_session.execute(
                text("SELECT consumed_at FROM refresh_tokens WHERE id = :id"),
                {"id": r1_id},
            )
            r1_consumed = r1_check.scalar_one()
            assert r1_consumed is not None

            # Successor children(R1) <= 1
            children_check = await check_session.execute(
                text("SELECT count(*) FROM refresh_tokens WHERE parent_token_id = :id"),
                {"id": r1_id},
            )
            assert children_check.scalar() == 1

            # Refresh session revoked_at IS NOT NULL (because Request B detected REUSE)
            s_check = await check_session.execute(
                text("SELECT revoked_at FROM refresh_sessions WHERE id = :id"),
                {"id": s1_id},
            )
            s_revoked = s_check.scalar_one()
            assert s_revoked is not None

        # Mandatory Final Assertion: Attempting refresh presenting R2 MUST FAIL because family was revoked
        service_post = SQLAlchemyRefreshSessionService(
            session_factory=factory,
            refresh_token_service=refresh_service,
            access_token_service=access_service,
            clock=clock,
        )
        with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
            await service_post.refresh(r2_raw)

    finally:
        if user_id:
            async with factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM refresh_tokens WHERE session_id = :id"),
                    {"id": s1_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM refresh_sessions WHERE id = :id"),
                    {"id": s1_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": user_id},
                )
                await cleanup_session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_refresh_rotation_postgres_real_rollback_on_r2_token_hash_collision() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    clock = SystemClock()
    priv_pem, pub_pem = generate_rsa_keys()
    access_service = JWTAccessTokenService(priv_pem, pub_pem, clock)

    email = f"rollback_rotate_{uuid4().hex[:8]}@example.com"
    user_id = None
    s1_id = uuid4()
    r1_id = uuid4()

    # Create real collision digest X
    collision_digest = b"collision_token_hash_digest_32b!"
    real_refresh_service = SecureRefreshTokenService()
    issued_r1 = real_refresh_service.issue()
    raw_r1 = issued_r1.raw_token
    now = clock.now()

    try:
        async with factory() as setup_session:
            user = User.create(email, UserRole.ANALYST)
            user_id = user.id
            await SQLAlchemyUserRepository(setup_session).add(user)

            s1_record = RefreshSessionRecord(
                id=s1_id,
                user_id=user.id,
                created_at=now,
                absolute_expires_at=now + timedelta(hours=8),
                revoked_at=None,
            )
            r1_record = RefreshTokenRecord(
                id=r1_id,
                session_id=s1_id,
                parent_token_id=None,
                token_hash=issued_r1.token_hash,
                issued_at=now,
                expires_at=now + timedelta(minutes=30),
                consumed_at=None,
            )

            # Insert an existing token with digest X to cause unique constraint collision on token_hash
            existing_collision_token = RefreshTokenRecord(
                id=uuid4(),
                session_id=s1_id,
                parent_token_id=None,
                token_hash=collision_digest,
                issued_at=now,
                expires_at=now + timedelta(minutes=30),
                consumed_at=None,
            )

            refresh_repo = SQLAlchemyRefreshRepository(setup_session)
            await refresh_repo.add_session(s1_record)
            await refresh_repo.add_token(r1_record)
            await refresh_repo.add_token(existing_collision_token)
            await setup_session.commit()

        # Controlled RefreshTokenService that proposes R2 digest == collision_digest
        class CollidingRefreshTokenService(SecureRefreshTokenService):
            def issue(self) -> Any:
                from app.application.security.refresh import IssuedRefreshToken
                return IssuedRefreshToken(
                    raw_token="colliding_raw_r2_token_string_43chars",
                    token_hash=collision_digest,
                )

        colliding_service = CollidingRefreshTokenService()
        service = SQLAlchemyRefreshSessionService(
            session_factory=factory,
            refresh_token_service=colliding_service,
            access_token_service=access_service,
            clock=clock,
        )

        # Attempting refresh triggers real PostgreSQL UNIQUE constraint collision on token_hash
        with pytest.raises((RefreshRepositoryError, RuntimeError)):
            await service.refresh(raw_r1)

        # Verify real PostgreSQL rollback after failure:
        # R1.consumed_at IS NULL, no R2 successor row committed, children(R1) == 0, session not revoked
        async with factory() as check_session:
            r1_check = await check_session.execute(
                text("SELECT consumed_at FROM refresh_tokens WHERE id = :id"),
                {"id": r1_id},
            )
            assert r1_check.scalar_one() is None

            children_check = await check_session.execute(
                text("SELECT count(*) FROM refresh_tokens WHERE parent_token_id = :id"),
                {"id": r1_id},
            )
            assert children_check.scalar() == 0

            s_check = await check_session.execute(
                text("SELECT revoked_at FROM refresh_sessions WHERE id = :id"),
                {"id": s1_id},
            )
            assert s_check.scalar_one() is None

    finally:
        if user_id:
            async with factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM refresh_tokens WHERE session_id = :id"),
                    {"id": s1_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM refresh_sessions WHERE id = :id"),
                    {"id": s1_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": user_id},
                )
                await cleanup_session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_refresh_rotation_postgres_consumed_after_expiry_precedence() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    real_clock = SystemClock()
    now_real = real_clock.now()

    priv_pem, pub_pem = generate_rsa_keys()
    access_service = JWTAccessTokenService(priv_pem, pub_pem, real_clock)
    refresh_service = SecureRefreshTokenService()

    email = f"consumed_exp_{uuid4().hex[:8]}@example.com"
    user_id = None
    s1_id = uuid4()
    r1_id = uuid4()

    issued_r1 = refresh_service.issue()
    raw_r1 = issued_r1.raw_token

    # Setup timestamps: R1 issued 50m ago, expired 20m ago, consumed 30m ago. Absolute session exp in 7h.
    t_created = now_real - timedelta(minutes=50)
    t_expired = now_real - timedelta(minutes=20)
    t_consumed = now_real - timedelta(minutes=30)
    t_abs_exp = now_real + timedelta(hours=7)

    try:
        async with factory() as setup_session:
            user = User.create(email, UserRole.ANALYST)
            user_id = user.id
            await SQLAlchemyUserRepository(setup_session).add(user)

            s1_record = RefreshSessionRecord(
                id=s1_id,
                user_id=user.id,
                created_at=t_created,
                absolute_expires_at=t_abs_exp,
                revoked_at=None,
            )
            r1_record = RefreshTokenRecord(
                id=r1_id,
                session_id=s1_id,
                parent_token_id=None,
                token_hash=issued_r1.token_hash,
                issued_at=t_created,
                expires_at=t_expired,  # EXPIRED
                consumed_at=t_consumed,  # ALSO CONSUMED
            )

            refresh_repo = SQLAlchemyRefreshRepository(setup_session)
            await refresh_repo.add_session(s1_record)
            await refresh_repo.add_token(r1_record)
            await setup_session.commit()

        service = SQLAlchemyRefreshSessionService(
            session_factory=factory,
            refresh_token_service=refresh_service,
            access_token_service=access_service,
            clock=real_clock,
        )

        # REUSE check MUST win over token expiry
        with pytest.raises(RefreshAuthenticationError, match="refresh authentication failed"):
            await service.refresh(raw_r1)

        # Verify PostgreSQL state: family revoked and committed
        async with factory() as check_session:
            s_check = await check_session.execute(
                text("SELECT revoked_at FROM refresh_sessions WHERE id = :id"),
                {"id": s1_id},
            )
            s_revoked = s_check.scalar_one()
            assert s_revoked is not None

    finally:
        if user_id:
            async with factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM refresh_tokens WHERE session_id = :id"),
                    {"id": s1_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM refresh_sessions WHERE id = :id"),
                    {"id": s1_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": user_id},
                )
                await cleanup_session.commit()

    await engine.dispose()
