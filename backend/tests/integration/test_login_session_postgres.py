import asyncio
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.application.security.credentials import PasswordCredential
from app.application.security.sessions import AuthSessionTokens
from app.core.config import get_settings
from app.domain.entities.user import User, UserRole
from app.infrastructure.database.engine import create_database_engine
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.repositories.sqlalchemy_credential_repository import (
    SQLAlchemyCredentialRepository,
)
from app.infrastructure.repositories.sqlalchemy_refresh_repository import (
    SQLAlchemyRefreshRepository,
)
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.infrastructure.security.argon2_password_hasher import (
    Argon2idPasswordHasher,
)
from app.infrastructure.security.jwt_access_token_service import (
    JWTAccessTokenService,
)
from app.infrastructure.security.refresh_token_service import (
    SecureRefreshTokenService,
)
from app.infrastructure.security.sqlalchemy_login_session_service import (
    SQLAlchemyLoginSessionService,
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

DUMMY_PHC = (
    "$argon2id$v=19$m=65536,t=3,p=4$Fl1Grf6vpX5SKg0514uA/w$"
    "B1b6Q8zwVQTD9GWQzzk6qXlmaYCjPcfUXI1rbfTDKRo"
)

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


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


def _run_alembic(*args: str) -> None:
    env = os.environ.copy()
    db_url = env.get("DATABASE_URL")
    if not db_url:
        try:
            settings = get_settings()
            if settings.database_url:
                db_url = str(settings.database_url)
        except Exception:
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


class FrozenTestClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


@pytest.mark.asyncio
async def test_login_session_postgres_durable_session_creation_and_contracts() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    clock_now = datetime.now(UTC)
    clock = FrozenTestClock(clock_now)
    hasher = Argon2idPasswordHasher(settings)
    priv_pem, pub_pem = generate_rsa_keys()
    access_service = JWTAccessTokenService(priv_pem, pub_pem, clock)
    refresh_service = SecureRefreshTokenService()

    email = f"login_pg_{uuid4().hex[:8]}@example.com"
    raw_pwd = "SecretPassword123!"
    pwd_hash = hasher.hash(raw_pwd)

    user_id = None
    try:
        # Setup test user and credential in database
        async with factory() as setup_session:
            user_repo = SQLAlchemyUserRepository(setup_session)
            cred_repo = SQLAlchemyCredentialRepository(setup_session)

            user = User.create(email, UserRole.ANALYST)
            user_id = user.id
            await user_repo.add(user)
            await cred_repo.add(
                PasswordCredential(user_id=user.id, password_hash=pwd_hash)
            )
            await setup_session.commit()

        # Perform login
        service = SQLAlchemyLoginSessionService(
            session_factory=factory,
            password_hasher=hasher,
            access_token_service=access_service,
            refresh_token_service=refresh_service,
            clock=clock,
            dummy_password_hash=DUMMY_PHC,
        )

        tokens = await service.login(email, raw_pwd)

        # Assertion 1: AuthSessionTokens returned
        assert isinstance(tokens, AuthSessionTokens)
        assert isinstance(tokens.access_token, str) and tokens.access_token
        assert isinstance(tokens.refresh_token, str) and tokens.refresh_token

        # Assertion 2, 3, 4, 7, 8, 9, 10: Verify committed S1 and R1 in fresh independent session
        async with factory() as check_session:
            # Query sessions
            s_rows = await check_session.execute(
                text(
                    """
                    SELECT id, user_id, created_at, absolute_expires_at, revoked_at
                    FROM refresh_sessions
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            )
            s_list = list(s_rows)
            assert len(s_list) == 1
            s1_id, s1_user_id, s1_created, s1_abs_exp, s1_revoked = s_list[0]

            assert s1_user_id == user_id
            assert s1_revoked is None
            assert abs((s1_abs_exp - s1_created).total_seconds() - 8 * 3600) < 1

            # Query tokens
            t_rows = await check_session.execute(
                text(
                    """
                    SELECT id, session_id, parent_token_id, token_hash, issued_at, expires_at, consumed_at
                    FROM refresh_tokens
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": s1_id},
            )
            t_list = list(t_rows)
            assert len(t_list) == 1
            (
                r1_id,
                r1_session_id,
                r1_parent_id,
                r1_hash,
                r1_issued,
                r1_exp,
                r1_consumed,
            ) = t_list[0]

            assert r1_session_id == s1_id
            assert r1_parent_id is None
            assert r1_consumed is None

            assert r1_exp <= s1_abs_exp
            assert abs((r1_exp - r1_issued).total_seconds() - 30 * 60) < 1

            # Assertion 5 & 6: Persisted token_hash is digest only; raw R1 string does not exist in DB
            digest = refresh_service.digest(tokens.refresh_token)
            assert bytes(r1_hash) == digest
            assert tokens.refresh_token not in str(t_list)
            assert tokens.refresh_token not in str(s_list)

            raw_search = await check_session.execute(
                text(
                    """
                    SELECT count(*) FROM refresh_tokens
                    WHERE encode(token_hash, 'hex') LIKE :raw
                    """
                ),
                {"raw": f"%{tokens.refresh_token}%"},
            )
            assert raw_search.scalar() == 0

    finally:
        if user_id:
            async with factory() as cleanup_session:
                await cleanup_session.execute(
                    text(
                        "DELETE FROM refresh_tokens WHERE session_id IN (SELECT id FROM refresh_sessions WHERE user_id = :id)"
                    ),
                    {"id": user_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM refresh_sessions WHERE user_id = :id"),
                    {"id": user_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM user_credentials WHERE user_id = :id"),
                    {"id": user_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": user_id},
                )
                await cleanup_session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_login_session_postgres_forced_failure_rolls_back_core_transaction() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    clock = SystemClock()
    hasher = Argon2idPasswordHasher(settings)
    priv_pem, pub_pem = generate_rsa_keys()
    access_service = JWTAccessTokenService(priv_pem, pub_pem, clock)
    refresh_service = SecureRefreshTokenService()

    email = f"rollback_pg_{uuid4().hex[:8]}@example.com"
    raw_pwd = "SecretPassword123!"

    class FailingRefreshRepo(SQLAlchemyRefreshRepository):
        async def add_token(self, record: Any) -> None:
            raise RuntimeError("Forced DB constraint failure on add_token")

    user_id = None
    try:
        async with factory() as setup_session:
            user_repo = SQLAlchemyUserRepository(setup_session)
            cred_repo = SQLAlchemyCredentialRepository(setup_session)
            user = User.create(email, UserRole.ANALYST)
            user_id = user.id
            await user_repo.add(user)
            await cred_repo.add(
                PasswordCredential(user_id=user.id, password_hash=hasher.hash(raw_pwd))
            )
            await setup_session.commit()

        service = SQLAlchemyLoginSessionService(
            session_factory=factory,
            password_hasher=hasher,
            access_token_service=access_service,
            refresh_token_service=refresh_service,
            clock=clock,
            dummy_password_hash=DUMMY_PHC,
            refresh_repo=FailingRefreshRepo,
        )

        with pytest.raises(RuntimeError, match="session creation failed"):
            await service.login(email, raw_pwd)

        async with factory() as check_session:
            s_rows = await check_session.execute(
                text("SELECT count(*) FROM refresh_sessions WHERE user_id = :id"),
                {"id": user_id},
            )
            assert s_rows.scalar() == 0
    finally:
        if user_id:
            async with factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM user_credentials WHERE user_id = :id"),
                    {"id": user_id},
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": user_id},
                )
                await cleanup_session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_login_session_postgres_rehash_after_commit_and_isolation() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    clock = SystemClock()
    priv_pem, pub_pem = generate_rsa_keys()
    access_service = JWTAccessTokenService(priv_pem, pub_pem, clock)
    refresh_service = SecureRefreshTokenService()

    class CustomHasher(Argon2idPasswordHasher):
        def needs_rehash(self, encoded_hash: str) -> bool:
            return True

    hasher = CustomHasher(settings)

    email = f"rehash_pg_{uuid4().hex[:8]}@example.com"
    raw_pwd = "SecretPassword123!"
    old_phc = "$argon2id$v=19$m=65536,t=3,p=4$old_salt$old_hash_bytes_value"

    user_id = None
    user2_id = None

    try:
        async with factory() as setup_session:
            user_repo = SQLAlchemyUserRepository(setup_session)
            cred_repo = SQLAlchemyCredentialRepository(setup_session)
            user = User.create(email, UserRole.ADMIN)
            user_id = user.id
            await user_repo.add(user)
            await setup_session.execute(
                text(
                    """
                    INSERT INTO user_credentials (user_id, password_hash)
                    VALUES (:id, :hash)
                    """
                ),
                {"id": user_id, "hash": old_phc},
            )
            await setup_session.commit()

        service = SQLAlchemyLoginSessionService(
            session_factory=factory,
            password_hasher=hasher,
            access_token_service=access_service,
            refresh_token_service=refresh_service,
            clock=clock,
            dummy_password_hash=DUMMY_PHC,
        )

        hasher.verify = lambda pwd, h: True  # type: ignore[assignment]

        tokens = await service.login(email, raw_pwd)
        assert isinstance(tokens, AuthSessionTokens)

        async with factory() as check_session:
            c_row = await check_session.execute(
                text("SELECT password_hash FROM user_credentials WHERE user_id = :id"),
                {"id": user_id},
            )
            new_hash = c_row.scalar_one()
            assert new_hash != old_phc

            s_count = await check_session.execute(
                text("SELECT count(*) FROM refresh_sessions WHERE user_id = :id"),
                {"id": user_id},
            )
            assert s_count.scalar() == 1

        email2 = f"rehash_fail_{uuid4().hex[:8]}@example.com"

        async with factory() as setup2_session:
            user2 = User.create(email2, UserRole.ANALYST)
            user2_id = user2.id
            await SQLAlchemyUserRepository(setup2_session).add(user2)
            await setup2_session.execute(
                text(
                    "INSERT INTO user_credentials (user_id, password_hash) VALUES (:id, :hash)"
                ),
                {"id": user2_id, "hash": old_phc},
            )
            await setup2_session.commit()

        class FailingCredRepo(SQLAlchemyCredentialRepository):
            async def replace_hash(
                self, user_id: Any, expected_hash: Any, replacement_hash: Any
            ) -> bool:
                raise RuntimeError("Forced rehash maintenance DB error")

        service2 = SQLAlchemyLoginSessionService(
            session_factory=factory,
            password_hasher=hasher,
            access_token_service=access_service,
            refresh_token_service=refresh_service,
            clock=clock,
            dummy_password_hash=DUMMY_PHC,
            cred_repo=FailingCredRepo,
        )

        tokens2 = await service2.login(email2, raw_pwd)
        assert isinstance(tokens2, AuthSessionTokens)

        async with factory() as check2_session:
            s2_count = await check2_session.execute(
                text("SELECT count(*) FROM refresh_sessions WHERE user_id = :id"),
                {"id": user2_id},
            )
            assert s2_count.scalar() == 1

    finally:
        ids_to_clean = [i for i in [user_id, user2_id] if i is not None]
        if ids_to_clean:
            async with factory() as cleanup_session:
                for uid in ids_to_clean:
                    await cleanup_session.execute(
                        text(
                            "DELETE FROM refresh_tokens WHERE session_id IN (SELECT id FROM refresh_sessions WHERE user_id = :id)"
                        ),
                        {"id": uid},
                    )
                    await cleanup_session.execute(
                        text("DELETE FROM refresh_sessions WHERE user_id = :id"),
                        {"id": uid},
                    )
                    await cleanup_session.execute(
                        text("DELETE FROM user_credentials WHERE user_id = :id"),
                        {"id": uid},
                    )
                    await cleanup_session.execute(
                        text("DELETE FROM users WHERE id = :id"),
                        {"id": uid},
                    )
                await cleanup_session.commit()

    await engine.dispose()
