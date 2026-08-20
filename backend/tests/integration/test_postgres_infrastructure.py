import os
from collections.abc import Generator

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
        reason="NEUROFIN_RUN_POSTGRES_INTEGRATION != '1'. Integration tests skipped by default.",
    ),
]


@pytest.fixture(autouse=True)
def _setup_database_url(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    db_url = os.environ.get("NEUROFIN_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if db_url:
        monkeypatch.setenv("DATABASE_URL", db_url)
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()
    else:
        yield


@pytest.mark.asyncio
async def test_pg01_real_connectivity() -> None:
    settings = get_settings()
    assert settings.database_url is not None, "DATABASE_URL must be set for integration tests"

    engine = create_database_engine(settings)
    try:
        async with engine.connect() as conn:
            db_res = await conn.execute(text("SELECT current_database()"))
            db_name = db_res.scalar()

            user_res = await conn.execute(text("SELECT current_user"))
            user_name = user_res.scalar()

            ver_res = await conn.execute(text("SELECT current_setting('server_version')"))
            server_version = str(ver_res.scalar())

            pid_res = await conn.execute(text("SELECT pg_backend_pid()"))
            pid = pid_res.scalar()

            assert db_name == "neurofin_nf_data_01_f"
            assert user_name == "neurofin_nf_data_01_f"
            assert server_version.startswith("18.4")
            assert isinstance(pid, int) and pid > 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_pg02_async_session_execution() -> None:
    settings = get_settings()
    assert settings.database_url is not None

    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    session = factory()

    try:
        res = await session.execute(text("SELECT current_database()"))
        db_name = res.scalar()
        assert db_name == "neurofin_nf_data_01_f"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_pg03_concurrent_session_isolation() -> None:
    settings = get_settings()
    assert settings.database_url is not None

    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    session_a = factory()
    session_b = factory()

    try:
        res_a = await session_a.execute(text("SELECT pg_backend_pid()"))
        pid_a = res_a.scalar()

        res_b = await session_b.execute(text("SELECT pg_backend_pid()"))
        pid_b = res_b.scalar()

        assert pid_a != pid_b, f"Expected independent connection PIDs, got {pid_a} == {pid_b}"
    finally:
        await session_a.close()
        await session_b.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_pg04_transaction_rollback() -> None:
    settings = get_settings()
    assert settings.database_url is not None

    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    session = factory()

    try:
        # 1. Baseline
        base_res = await session.execute(text("SELECT current_setting('application_name')"))
        baseline_val = base_res.scalar()

        # 2. In-transaction modification
        await session.execute(text("SET LOCAL application_name = 'nf_data_01_f_probe'"))

        # 3. Confirm in-transaction
        probe_res = await session.execute(text("SELECT current_setting('application_name')"))
        assert probe_res.scalar() == "nf_data_01_f_probe"

        # 4. Rollback
        await session.rollback()

        # 5. Post-rollback confirmation
        post_res = await session.execute(text("SELECT current_setting('application_name')"))
        post_val = post_res.scalar()

        assert post_val == baseline_val
        assert post_val != "nf_data_01_f_probe"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_pg05_alembic_version_final() -> None:
    settings = get_settings()
    assert settings.database_url is not None

    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    session = factory()

    try:
        res = await session.execute(text("SELECT version_num FROM alembic_version"))
        version_num = res.scalar()
        assert version_num == "116464527395"
    finally:
        await session.close()
        await engine.dispose()
