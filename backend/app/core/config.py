from functools import lru_cache
from typing import Annotated, Any

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NeuroFin Forecast API"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    allowed_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    default_forecast_horizon: int = 12
    database_url: PostgresDsn | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: PostgresDsn | None) -> PostgresDsn | None:
        if value is None:
            return None

        if value.scheme != "postgresql+asyncpg":
            raise ValueError(
                "DATABASE_URL must use the 'postgresql+asyncpg' scheme for PostgreSQL async driver."
            )

        hosts = value.hosts()
        if not hosts or not hosts[0].get("host"):
            raise ValueError("DATABASE_URL must include a valid host.")

        path = value.path
        if not path or path.strip("/") == "":
            raise ValueError("DATABASE_URL must include a database name in the path.")

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
