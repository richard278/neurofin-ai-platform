from functools import lru_cache
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_version: str
    api_prefix: str
    allowed_origins: list[str]
    default_forecast_horizon: int


@lru_cache
def get_settings() -> Settings:
    raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    allowed_origins = [item.strip() for item in raw_origins.split(",") if item.strip()]

    return Settings(
        app_name=os.getenv("APP_NAME", "NeuroFin Forecast API"),
        app_env=os.getenv("APP_ENV", "development"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        api_prefix=os.getenv("API_PREFIX", "/api/v1"),
        allowed_origins=allowed_origins,
        default_forecast_horizon=int(os.getenv("DEFAULT_FORECAST_HORIZON", "12")),
    )
