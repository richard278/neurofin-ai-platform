import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.delenv("API_PREFIX", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("DEFAULT_FORECAST_HORIZON", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    get_settings.cache_clear()
    settings = Settings(_env_file=None)

    assert settings.app_name == "NeuroFin Forecast API"
    assert settings.app_env == "development"
    assert settings.app_version == "0.1.0"
    assert settings.api_prefix == "/api/v1"
    assert settings.allowed_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert settings.default_forecast_horizon == 12
    assert settings.database_url is None


def test_allowed_origins_csv_parsing() -> None:
    settings = Settings(ALLOWED_ORIGINS="http://a.example,http://b.example", _env_file=None)  # type: ignore[call-arg]
    assert settings.allowed_origins == ["http://a.example", "http://b.example"]
    assert isinstance(settings.allowed_origins, list)
    assert all(isinstance(item, str) for item in settings.allowed_origins)


def test_allowed_origins_trimming_and_filtering() -> None:
    settings = Settings(ALLOWED_ORIGINS="http://a.example, http://b.example,, ", _env_file=None)  # type: ignore[call-arg]
    assert settings.allowed_origins == ["http://a.example", "http://b.example"]
    assert isinstance(settings.allowed_origins, list)
    assert all(isinstance(item, str) for item in settings.allowed_origins)


def test_allowed_origins_internal_type() -> None:
    settings = Settings(_env_file=None)
    assert isinstance(settings.allowed_origins, list)
    assert all(isinstance(origin, str) for origin in settings.allowed_origins)


def test_database_url_absent() -> None:
    settings = Settings(DATABASE_URL=None, _env_file=None)  # type: ignore[call-arg]
    assert settings.database_url is None


def test_database_url_valid_postgresql_async() -> None:
    url = "postgresql+asyncpg://user:password@localhost:5432/neurofin"
    settings = Settings(DATABASE_URL=url, _env_file=None)  # type: ignore[call-arg]
    assert settings.database_url is not None
    assert str(settings.database_url) == url
    assert settings.database_url.scheme == "postgresql+asyncpg"


def test_database_url_incomplete_dsn() -> None:
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql+asyncpg://", _env_file=None)  # type: ignore[call-arg]


def test_database_url_missing_database() -> None:
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432", _env_file=None)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/", _env_file=None)  # type: ignore[call-arg]


def test_database_url_incorrect_postgres_driver() -> None:
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql://user:password@localhost:5432/neurofin", _env_file=None)  # type: ignore[call-arg]


def test_database_url_other_postgres_driver() -> None:
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/neurofin", _env_file=None)  # type: ignore[call-arg]


def test_database_url_sqlite_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="sqlite:///test.db", _env_file=None)  # type: ignore[call-arg]


def test_environment_variable_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Custom Platform Name")
    monkeypatch.setenv("DEFAULT_FORECAST_HORIZON", "24")

    get_settings.cache_clear()
    settings = Settings(_env_file=None)

    assert settings.app_name == "Custom Platform Name"
    assert settings.default_forecast_horizon == 24
