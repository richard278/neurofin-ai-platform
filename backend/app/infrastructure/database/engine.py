from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL must be configured to create a database engine.")

    return create_async_engine(str(settings.database_url))
