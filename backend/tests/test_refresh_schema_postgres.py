import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

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

BACKEND_DIR = Path(__file__).parents[1]


def _run_alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        check=True,
    )


def _get_sqlstate(exc: Exception) -> str | None:
    if isinstance(exc, DBAPIError) and exc.orig is not None:
        return getattr(exc.orig, "sqlstate", None)
    return getattr(exc, "sqlstate", None)


@pytest.fixture(autouse=True)
def _setup_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    db_url = os.environ.get("NEUROFIN_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if db_url:
        monkeypatch.setenv("DATABASE_URL", db_url)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_upgrade_a002_creates_tables_and_exact_schema_in_postgres() -> None:
    _run_alembic("upgrade", "20260829a002")

    settings = get_settings()
    engine = create_database_engine(settings)

    try:
        async with engine.connect() as conn:
            curr_res = await conn.execute(text("SELECT version_num FROM alembic_version"))
            assert curr_res.scalar() == "20260829a002"

            def inspect_db(sync_conn: Connection) -> dict[str, Any]:
                inspector = inspect(sync_conn)
                tables = inspector.get_table_names(schema="public")
                return {
                    "tables": sorted(tables),
                    "rs_columns": inspector.get_columns("refresh_sessions", schema="public"),
                    "rt_columns": inspector.get_columns("refresh_tokens", schema="public"),
                    "rs_pks": inspector.get_pk_constraint("refresh_sessions", schema="public"),
                    "rt_pks": inspector.get_pk_constraint("refresh_tokens", schema="public"),
                    "rs_fks": inspector.get_foreign_keys("refresh_sessions", schema="public"),
                    "rt_fks": inspector.get_foreign_keys("refresh_tokens", schema="public"),
                    "rs_uqs": inspector.get_unique_constraints("refresh_sessions", schema="public"),
                    "rt_uqs": inspector.get_unique_constraints("refresh_tokens", schema="public"),
                    "rs_indexes": inspector.get_indexes("refresh_sessions", schema="public"),
                    "rt_indexes": inspector.get_indexes("refresh_tokens", schema="public"),
                    "rs_checks": inspector.get_check_constraints("refresh_sessions", schema="public"),
                    "rt_checks": inspector.get_check_constraints("refresh_tokens", schema="public"),
                }

            data = await conn.run_sync(inspect_db)

            assert "refresh_sessions" in data["tables"]
            assert "refresh_tokens" in data["tables"]
            assert "users" in data["tables"]

            # Column verification
            rs_col_map = {c["name"]: c for c in data["rs_columns"]}
            assert list(rs_col_map.keys()) == ["id", "user_id", "created_at", "absolute_expires_at", "revoked_at"]
            assert rs_col_map["id"]["nullable"] is False
            assert rs_col_map["user_id"]["nullable"] is False
            assert rs_col_map["created_at"]["nullable"] is False
            assert rs_col_map["absolute_expires_at"]["nullable"] is False
            assert rs_col_map["revoked_at"]["nullable"] is True

            rt_col_map = {c["name"]: c for c in data["rt_columns"]}
            assert list(rt_col_map.keys()) == ["id", "session_id", "parent_token_id", "token_hash", "issued_at", "expires_at", "consumed_at"]
            assert rt_col_map["id"]["nullable"] is False
            assert rt_col_map["session_id"]["nullable"] is False
            assert rt_col_map["parent_token_id"]["nullable"] is True
            assert rt_col_map["token_hash"]["nullable"] is False
            assert rt_col_map["issued_at"]["nullable"] is False
            assert rt_col_map["expires_at"]["nullable"] is False
            assert rt_col_map["consumed_at"]["nullable"] is True

            # Zero defaults/server_defaults
            for col in data["rs_columns"] + data["rt_columns"]:
                assert col.get("default") is None

            # PK constraints
            assert data["rs_pks"]["name"] == "pk_refresh_sessions"
            assert data["rt_pks"]["name"] == "pk_refresh_tokens"

            # FK constraints (3 total)
            rs_fk_names = [fk["name"] for fk in data["rs_fks"]]
            rt_fk_names = [fk["name"] for fk in data["rt_fks"]]
            assert rs_fk_names == ["fk_refresh_sessions_user_id_users"]
            assert sorted(rt_fk_names) == sorted([
                "fk_refresh_tokens_session_id_refresh_sessions",
                "fk_refresh_tokens_parent_token_id_refresh_tokens",
            ])

            # Check no-cascade in FKs
            for fk in data["rs_fks"] + data["rt_fks"]:
                ondelete = fk.get("options", {}).get("ondelete")
                assert ondelete is None or ondelete.upper() in ("NO ACTION", "RESTRICT")

            # Unique constraints
            rt_uq_names = sorted([uq["name"] for uq in data["rt_uqs"]])
            assert rt_uq_names == sorted(["uq_refresh_tokens_token_hash", "uq_refresh_tokens_parent_token_id"])

            # Check constraints
            rs_ck_names = [ck["name"] for ck in data["rs_checks"]]
            rt_ck_names = sorted([ck["name"] for ck in data["rt_checks"]])
            assert rs_ck_names == ["ck_refresh_sessions_absolute_expiry"]
            assert rt_ck_names == sorted(["ck_refresh_tokens_hash_length", "ck_refresh_tokens_expiry"])

            # Indexes (zero additional outside PK/UQ)
            rs_extra_indexes = [idx for idx in data["rs_indexes"] if not idx.get("duplicates_constraint")]
            rt_extra_indexes = [idx for idx in data["rt_indexes"] if not idx.get("duplicates_constraint")]
            assert len(rs_extra_indexes) == 0
            assert len(rt_extra_indexes) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgres_constraint_enforcement_matrix() -> None:
    _run_alembic("upgrade", "20260829a002")

    settings = get_settings()
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    user_id: UUID = uuid4()
    session_id: UUID = uuid4()
    root_token_id: UUID = uuid4()
    child_token_id: UUID = uuid4()

    valid_hash_1 = bytes(range(32))
    valid_hash_2 = bytes(range(31, -1, -1))
    valid_hash_3 = bytes([(x * 3) % 256 for x in range(32)])

    now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    expiry_session = datetime(2026, 8, 31, 20, 0, tzinfo=UTC)
    expiry_token = datetime(2026, 8, 31, 12, 30, tzinfo=UTC)

    async with factory() as session:
        # Create base user
        await session.execute(
            text(
                "INSERT INTO users (id, email, role) "
                "VALUES (:id, :email, :role)"
            ),
            {
                "id": user_id,
                "email": f"test_{user_id.hex[:8]}@example.com",
                "role": "ANALYST",
            },
        )
        await session.commit()

        # Create valid session
        await session.execute(
            text(
                "INSERT INTO refresh_sessions (id, user_id, created_at, absolute_expires_at) "
                "VALUES (:id, :user_id, :created_at, :expires_at)"
            ),
            {
                "id": session_id,
                "user_id": user_id,
                "created_at": now,
                "expires_at": expiry_session,
            },
        )

        # Create valid root token
        await session.execute(
            text(
                "INSERT INTO refresh_tokens (id, session_id, parent_token_id, token_hash, issued_at, expires_at) "
                "VALUES (:id, :session_id, NULL, :token_hash, :issued_at, :expires_at)"
            ),
            {
                "id": root_token_id,
                "session_id": session_id,
                "token_hash": valid_hash_1,
                "issued_at": now,
                "expires_at": expiry_token,
            },
        )

        # Create valid child token
        await session.execute(
            text(
                "INSERT INTO refresh_tokens (id, session_id, parent_token_id, token_hash, issued_at, expires_at) "
                "VALUES (:id, :session_id, :parent_token_id, :token_hash, :issued_at, :expires_at)"
            ),
            {
                "id": child_token_id,
                "session_id": session_id,
                "parent_token_id": root_token_id,
                "token_hash": valid_hash_2,
                "issued_at": now,
                "expires_at": expiry_token,
            },
        )
        await session.commit()

        async def _assert_violation(stmt: Any, params: dict[str, Any], expected_sqlstate: str) -> None:
            async with session.begin_nested() as savepoint:
                with pytest.raises(SQLAlchemyError) as exc_info:
                    await session.execute(stmt, params)
                assert _get_sqlstate(exc_info.value) == expected_sqlstate
                await savepoint.rollback()

        # Matrix violation 1: fk_refresh_sessions_user_id_users (23503)
        await _assert_violation(
            text(
                "INSERT INTO refresh_sessions (id, user_id, created_at, absolute_expires_at) "
                "VALUES (:id, :user_id, :created_at, :expires_at)"
            ),
            {"id": uuid4(), "user_id": uuid4(), "created_at": now, "expires_at": expiry_session},
            "23503",
        )

        # Matrix violation 2: ck_refresh_sessions_absolute_expiry (23514)
        await _assert_violation(
            text(
                "INSERT INTO refresh_sessions (id, user_id, created_at, absolute_expires_at) "
                "VALUES (:id, :user_id, :created_at, :expires_at)"
            ),
            {"id": uuid4(), "user_id": user_id, "created_at": expiry_session, "expires_at": now},
            "23514",
        )

        # Matrix violation 3: fk_refresh_tokens_session_id_refresh_sessions (23503)
        await _assert_violation(
            text(
                "INSERT INTO refresh_tokens (id, session_id, parent_token_id, token_hash, issued_at, expires_at) "
                "VALUES (:id, :session_id, NULL, :token_hash, :issued_at, :expires_at)"
            ),
            {"id": uuid4(), "session_id": uuid4(), "token_hash": valid_hash_3, "issued_at": now, "expires_at": expiry_token},
            "23503",
        )

        # Matrix violation 4: fk_refresh_tokens_parent_token_id_refresh_tokens (23503)
        await _assert_violation(
            text(
                "INSERT INTO refresh_tokens (id, session_id, parent_token_id, token_hash, issued_at, expires_at) "
                "VALUES (:id, :session_id, :parent_token_id, :token_hash, :issued_at, :expires_at)"
            ),
            {"id": uuid4(), "session_id": session_id, "parent_token_id": uuid4(), "token_hash": valid_hash_3, "issued_at": now, "expires_at": expiry_token},
            "23503",
        )

        # Matrix violation 5: ck_refresh_tokens_hash_length (23514)
        await _assert_violation(
            text(
                "INSERT INTO refresh_tokens (id, session_id, parent_token_id, token_hash, issued_at, expires_at) "
                "VALUES (:id, :session_id, NULL, :token_hash, :issued_at, :expires_at)"
            ),
            {"id": uuid4(), "session_id": session_id, "token_hash": b"short_hash", "issued_at": now, "expires_at": expiry_token},
            "23514",
        )

        # Matrix violation 6: ck_refresh_tokens_expiry (23514)
        await _assert_violation(
            text(
                "INSERT INTO refresh_tokens (id, session_id, parent_token_id, token_hash, issued_at, expires_at) "
                "VALUES (:id, :session_id, NULL, :token_hash, :issued_at, :expires_at)"
            ),
            {"id": uuid4(), "session_id": session_id, "token_hash": valid_hash_3, "issued_at": expiry_token, "expires_at": now},
            "23514",
        )

        # Matrix violation 7: uq_refresh_tokens_token_hash (23505)
        await _assert_violation(
            text(
                "INSERT INTO refresh_tokens (id, session_id, parent_token_id, token_hash, issued_at, expires_at) "
                "VALUES (:id, :session_id, NULL, :token_hash, :issued_at, :expires_at)"
            ),
            {"id": uuid4(), "session_id": session_id, "token_hash": valid_hash_1, "issued_at": now, "expires_at": expiry_token},
            "23505",
        )

        # Matrix violation 8: uq_refresh_tokens_parent_token_id (23505)
        await _assert_violation(
            text(
                "INSERT INTO refresh_tokens (id, session_id, parent_token_id, token_hash, issued_at, expires_at) "
                "VALUES (:id, :session_id, :parent_token_id, :token_hash, :issued_at, :expires_at)"
            ),
            {"id": uuid4(), "session_id": session_id, "parent_token_id": root_token_id, "token_hash": valid_hash_3, "issued_at": now, "expires_at": expiry_token},
            "23505",
        )

        # No-cascade check: deleting session referenced by tokens must fail with 23503
        await _assert_violation(
            text("DELETE FROM refresh_sessions WHERE id = :id"),
            {"id": session_id},
            "23503",
        )

    await engine.dispose()


@pytest.mark.asyncio
async def test_downgrade_a001_and_re_upgrade_a002() -> None:
    settings = get_settings()
    engine = create_database_engine(settings)

    try:
        # Downgrade to 20260829a001
        _run_alembic("downgrade", "20260829a001")

        async with engine.connect() as conn:
            curr_res = await conn.execute(text("SELECT version_num FROM alembic_version"))
            assert curr_res.scalar() == "20260829a001"

            def inspect_downgrade(sync_conn: Connection) -> list[str]:
                inspector = inspect(sync_conn)
                return sorted(inspector.get_table_names(schema="public"))

            tables_down = await conn.run_sync(inspect_downgrade)
            assert "refresh_sessions" not in tables_down
            assert "refresh_tokens" not in tables_down
            assert "users" in tables_down
    finally:
        # Re-upgrade to 20260829a002 in finally block to ensure state restoration
        _run_alembic("upgrade", "20260829a002")

        async with engine.connect() as conn:
            curr_res = await conn.execute(text("SELECT version_num FROM alembic_version"))
            assert curr_res.scalar() == "20260829a002"

            def inspect_reup(sync_conn: Connection) -> list[str]:
                inspector = inspect(sync_conn)
                return sorted(inspector.get_table_names(schema="public"))

            tables_up = await conn.run_sync(inspect_reup)
            assert "refresh_sessions" in tables_up
            assert "refresh_tokens" in tables_up
            assert "users" in tables_up

        await engine.dispose()
