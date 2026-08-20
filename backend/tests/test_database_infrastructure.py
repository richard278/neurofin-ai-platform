import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.infrastructure.database.engine import create_database_engine
from app.infrastructure.database.session import create_session_factory


def test_create_engine_database_url_absent() -> None:
    settings = Settings(_env_file=None)
    with pytest.raises(RuntimeError) as exc_info:
        create_database_engine(settings)

    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert "user" not in message.lower()
    assert "password" not in message.lower()


def test_create_engine_valid_database_url() -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/neurofin"
    settings = Settings(DATABASE_URL=url, _env_file=None)  # type: ignore[call-arg]
    engine = create_database_engine(settings)

    assert isinstance(engine, AsyncEngine)


def test_create_engine_drivername() -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/neurofin"
    settings = Settings(DATABASE_URL=url, _env_file=None)  # type: ignore[call-arg]
    engine = create_database_engine(settings)

    assert engine.url.drivername == "postgresql+asyncpg"


def test_create_session_factory() -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/neurofin"
    settings = Settings(DATABASE_URL=url, _env_file=None)  # type: ignore[call-arg]
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    assert isinstance(factory, async_sessionmaker)


def test_session_factory_produces_async_session() -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/neurofin"
    settings = Settings(DATABASE_URL=url, _env_file=None)  # type: ignore[call-arg]
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    session = factory()

    assert isinstance(session, AsyncSession)


def test_session_factory_expire_on_commit_is_false() -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/neurofin"
    settings = Settings(DATABASE_URL=url, _env_file=None)  # type: ignore[call-arg]
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    assert factory.kw.get("expire_on_commit") is False
