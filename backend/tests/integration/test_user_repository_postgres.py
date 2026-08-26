import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.core.config import get_settings
from app.domain.entities.user import User, UserRole
from app.domain.repositories.user_repository import UserAlreadyExistsError
from app.infrastructure.database.engine import create_database_engine
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.session import create_session_factory
from app.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
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


@pytest_asyncio.fixture
async def database():
    _run_alembic("upgrade", "head")

    settings = get_settings()
    assert settings.database_url is not None
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    async with factory() as cleanup_session:
        await cleanup_session.execute(delete(UserModel))
        await cleanup_session.commit()

    yield engine, factory

    async with factory() as cleanup_session:
        await cleanup_session.execute(delete(UserModel))
        await cleanup_session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_add_external_commit_and_read_back(database) -> None:
    _, factory = database
    user = User.create("user@example.com", UserRole.ANALYST)

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        await repository.add(user)
        await session.commit()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        assert await repository.get_by_id(user.id) == user
        assert await repository.get_by_email(user.email) == user
        assert await repository.get_by_id(uuid4()) is None
        assert await repository.get_by_email("missing@example.com") is None


@pytest.mark.asyncio
async def test_get_by_email_does_not_canonicalize(database) -> None:
    _, factory = database
    user = User.create("user@example.com", UserRole.ANALYST)

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        await repository.add(user)
        await session.commit()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        assert await repository.get_by_email("USER@EXAMPLE.COM") is None


@pytest.mark.asyncio
async def test_flush_does_not_commit_and_external_rollback_removes_insert(
    database,
) -> None:
    _, factory = database
    user = User.create("rollback@example.com", UserRole.ANALYST)

    session_a = factory()
    session_b = factory()

    try:
        repository_a = SQLAlchemyUserRepository(session_a)
        await repository_a.add(user)

        repository_b = SQLAlchemyUserRepository(session_b)
        assert await repository_b.get_by_id(user.id) is None

        await session_a.rollback()
    finally:
        await session_a.close()
        await session_b.close()

    async with factory() as session_c:
        repository_c = SQLAlchemyUserRepository(session_c)
        assert await repository_c.get_by_id(user.id) is None


@pytest.mark.asyncio
async def test_duplicate_email_translates_to_user_already_exists(database) -> None:
    _, factory = database
    first = User.create("duplicate@example.com", UserRole.ANALYST)
    second = User.create("duplicate@example.com", UserRole.ADMIN)

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        await repository.add(first)
        await session.commit()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await repository.add(second)

        assert exc_info.value.__cause__ is not None
        assert session.in_transaction()
        await session.rollback()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        assert await repository.get_by_id(first.id) == first
        assert await repository.get_by_id(second.id) is None


@pytest.mark.asyncio
async def test_duplicate_uuid_translates_to_user_already_exists(database) -> None:
    _, factory = database
    user_id = uuid4()
    first = User(id=user_id, email="first@example.com", role=UserRole.ANALYST)
    second = User(id=user_id, email="second@example.com", role=UserRole.ADMIN)

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        await repository.add(first)
        await session.commit()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        with pytest.raises(UserAlreadyExistsError) as exc_info:
            await repository.add(second)

        assert exc_info.value.__cause__ is not None
        assert session.in_transaction()
        await session.rollback()

    async with factory() as session:
        repository = SQLAlchemyUserRepository(session)
        assert await repository.get_by_email("first@example.com") == first
        assert await repository.get_by_email("second@example.com") is None
