import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.application.security.credentials import (
    CredentialAlreadyExistsError,
    PasswordCredential,
)
from app.core.config import get_settings
from app.infrastructure.database.engine import create_database_engine
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.repositories.sqlalchemy_credential_repository import (
    SQLAlchemyCredentialRepository,
)

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
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        check=True,
    )


@pytest.mark.asyncio
async def test_user_credentials_schema_matches_contract() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        table_rows = await session.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
        )
        assert [row[0] for row in table_rows] == [
            "alembic_version",
            "user_credentials",
            "users",
        ]

        column_rows = await session.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'user_credentials'
                ORDER BY ordinal_position
                """
            )
        )
        assert list(column_rows) == [
            ("user_id", "uuid", "NO"),
            ("password_hash", "text", "NO"),
        ]

        constraint_rows = await session.execute(
            text(
                """
                SELECT conname, contype
                FROM pg_constraint
                WHERE conrelid = 'public.user_credentials'::regclass
                ORDER BY conname
                """
            )
        )
        constraints = {
            row[0]: (row[1].decode("utf-8") if isinstance(row[1], bytes) else row[1])
            for row in constraint_rows
        }
        assert "pk_user_credentials" in constraints
        assert constraints["pk_user_credentials"] == "p"
        assert "fk_user_credentials_user_id_users" in constraints
        assert constraints["fk_user_credentials_user_id_users"] == "f"

        fk_rows = await session.execute(
            text(
                """
                SELECT
                    a_src.attname AS src_col,
                    c_ref.relname AS ref_table,
                    a_ref.attname AS ref_col
                FROM pg_constraint con
                JOIN pg_class c_src ON c_src.oid = con.conrelid
                JOIN pg_class c_ref ON c_ref.oid = con.confrelid
                JOIN pg_attribute a_src ON a_src.attrelid = con.conrelid AND a_src.attnum = con.conkey[1]
                JOIN pg_attribute a_ref ON a_ref.attrelid = con.confrelid AND a_ref.attnum = con.confkey[1]
                WHERE con.conname = 'fk_user_credentials_user_id_users'
                """
            )
        )
        assert list(fk_rows) == [("user_id", "users", "id")]

    await engine.dispose()


def test_user_credentials_migration_round_trip() -> None:
    _run_alembic("upgrade", "head")
    _run_alembic("downgrade", "20260824a001")
    try:
        settings = get_settings()
        assert settings.database_url is not None
        engine = create_database_engine(settings)
        factory = create_session_factory(engine)

        async def _check_downgraded_schema() -> None:
            async with factory() as session:
                rows = await session.execute(
                    text(
                        """
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                        ORDER BY tablename
                        """
                    )
                )
                tables = [row[0] for row in rows]
                assert "users" in tables
                assert "user_credentials" not in tables
            await engine.dispose()

        asyncio.run(_check_downgraded_schema())
    finally:
        _run_alembic("upgrade", "head")

    ini_path = BACKEND_DIR / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["20260829a001"]


@pytest.mark.asyncio
async def test_credential_repository_postgres_lifecycle_and_transaction_boundary() -> None:
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    user_id = uuid4()
    email = f"cred_test_{user_id.hex[:8]}@example.com"
    initial_hash = "$argon2id$v=19$m=65536,t=3,p=4$salt$hash1"
    updated_hash = "$argon2id$v=19$m=65536,t=3,p=4$salt$hash2"

    try:
        # Create parent user in users table
        async with factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO users (id, email, role)
                    VALUES (:id, :email, 'ANALYST')
                    """
                ),
                {"id": user_id, "email": email},
            )
            await session.commit()

        # 1. Add credential in Session A (uncommitted)
        async with factory() as session_a:
            repo_a = SQLAlchemyCredentialRepository(session_a)
            credential = PasswordCredential(user_id=user_id, password_hash=initial_hash)
            await repo_a.add(credential)

            # Uncommitted: not visible in Session B
            async with factory() as session_b:
                repo_b = SQLAlchemyCredentialRepository(session_b)
                missing = await repo_b.get_by_user_id(user_id)
                assert missing is None

            # Commit Session A
            await session_a.commit()

        # 2. Durable after commit
        async with factory() as session_c:
            repo_c = SQLAlchemyCredentialRepository(session_c)
            fetched = await repo_c.get_by_user_id(user_id)
            assert fetched == PasswordCredential(
                user_id=user_id, password_hash=initial_hash
            )

        # 3. Duplicate PK produces CredentialAlreadyExistsError
        async with factory() as session_dup:
            repo_dup = SQLAlchemyCredentialRepository(session_dup)
            with pytest.raises(CredentialAlreadyExistsError):
                await repo_dup.add(
                    PasswordCredential(user_id=user_id, password_hash="other_hash")
                )
            await session_dup.rollback()

        # 4. Rollback eliminates uncommitted addition
        user2_id = uuid4()
        user2_email = f"cred2_{user2_id.hex[:8]}@example.com"
        async with factory() as session_u2:
            await session_u2.execute(
                text("INSERT INTO users (id, email, role) VALUES (:id, :email, 'ANALYST')"),
                {"id": user2_id, "email": user2_email},
            )
            await session_u2.commit()

        try:
            async with factory() as session_rb:
                repo_rb = SQLAlchemyCredentialRepository(session_rb)
                await repo_rb.add(
                    PasswordCredential(user_id=user2_id, password_hash="uncommitted")
                )
                await session_rb.rollback()

            async with factory() as session_check_rb:
                repo_check = SQLAlchemyCredentialRepository(session_check_rb)
                assert await repo_check.get_by_user_id(user2_id) is None
        finally:
            async with factory() as session_del_u2:
                await session_del_u2.execute(
                    text("DELETE FROM user_credentials WHERE user_id = :id"),
                    {"id": user2_id},
                )
                await session_del_u2.execute(
                    text("DELETE FROM users WHERE id = :id"),
                    {"id": user2_id},
                )
                await session_del_u2.commit()

        # 5. replace_hash with stale expected hash does NOT overwrite
        async with factory() as session_rep:
            repo_rep = SQLAlchemyCredentialRepository(session_rep)

            # Stale expected hash returns False
            success_stale = await repo_rep.replace_hash(
                user_id=user_id,
                expected_hash="stale_expected_hash",
                replacement_hash=updated_hash,
            )
            assert success_stale is False

            # E4: Independent read proves password_hash is still initial_hash and not updated_hash
            async with factory() as session_check_stale:
                repo_check_stale = SQLAlchemyCredentialRepository(session_check_stale)
                current_stale = await repo_check_stale.get_by_user_id(user_id)
                assert current_stale == PasswordCredential(
                    user_id=user_id, password_hash=initial_hash
                )

            # E3: Valid replace_hash in Session Rep (uncommitted)
            success_valid = await repo_rep.replace_hash(
                user_id=user_id,
                expected_hash=initial_hash,
                replacement_hash=updated_hash,
            )
            assert success_valid is True

            # E3: Uncommitted replace_hash: independent Session B still observes initial_hash
            async with factory() as session_b_rep:
                repo_b_rep = SQLAlchemyCredentialRepository(session_b_rep)
                uncommitted_view = await repo_b_rep.get_by_user_id(user_id)
                assert uncommitted_view == PasswordCredential(
                    user_id=user_id, password_hash=initial_hash
                )

            # Commit Session Rep
            await session_rep.commit()

        # E3: Verify updated hash persisted in fresh session after commit
        async with factory() as session_ver:
            repo_ver = SQLAlchemyCredentialRepository(session_ver)
            updated = await repo_ver.get_by_user_id(user_id)
            assert updated == PasswordCredential(
                user_id=user_id, password_hash=updated_hash
            )

    finally:
        # Fixture cleanup in order: user_credentials -> users
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
