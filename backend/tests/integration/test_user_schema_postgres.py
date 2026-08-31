import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.infrastructure.database.engine import create_database_engine
from app.infrastructure.database.session import create_session_factory

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
async def test_users_schema_matches_contract() -> None:
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
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users'
                ORDER BY ordinal_position
                """
            )
        )
        assert list(column_rows) == [
            ("id", "uuid", "NO", None),
            ("email", "character varying", "NO", None),
            ("role", "character varying", "NO", None),
        ]

        constraint_rows = await session.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'public.users'::regclass
                  AND contype <> 'n'
                ORDER BY conname
                """
            )
        )
        assert {row[0] for row in constraint_rows} == {
            "ck_users_email_canonical",
            "ck_users_role",
            "pk_users",
            "uq_users_email",
        }

    await engine.dispose()


def test_users_migration_round_trip() -> None:
    _run_alembic("upgrade", "head")
    _run_alembic("downgrade", "116464527395")
    _run_alembic("upgrade", "head")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "role"),
    [
        ("User@example.com", "ANALYST"),
        (" user@example.com ", "ANALYST"),
        ("user@example.com", "SUPERADMIN"),
    ],
)
async def test_database_rejects_invalid_persisted_identity(
    email: str, role: str
) -> None:
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(
                    """
                    INSERT INTO users (id, email, role)
                    VALUES (:id, :email, :role)
                    """
                ),
                {"id": uuid4(), "email": email, "role": role},
            )
            await session.flush()
        await session.rollback()

    await engine.dispose()


@pytest.mark.asyncio
async def test_database_rejects_duplicate_canonical_email() -> None:
    from uuid import uuid4

    from sqlalchemy.exc import IntegrityError

    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    canonical_email = f"user_{uuid4().hex[:8]}@example.com"
    user_a_id = uuid4()
    user_b_id = uuid4()

    async with factory() as session_a:
        await session_a.execute(
            text(
                """
                INSERT INTO users (id, email, role)
                VALUES (:id, :email, :role)
                """
            ),
            {"id": user_a_id, "email": canonical_email, "role": "ANALYST"},
        )
        await session_a.commit()

    try:
        async with factory() as session_b:
            with pytest.raises(IntegrityError):
                await session_b.execute(
                    text(
                        """
                        INSERT INTO users (id, email, role)
                        VALUES (:id, :email, :role)
                        """
                    ),
                    {"id": user_b_id, "email": canonical_email, "role": "ANALYST"},
                )
                await session_b.flush()
            await session_b.rollback()
    finally:
        async with factory() as cleanup_session:
            await cleanup_session.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": user_a_id},
            )
            await cleanup_session.commit()

    await engine.dispose()
