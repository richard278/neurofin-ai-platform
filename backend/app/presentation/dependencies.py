from functools import lru_cache

from fastapi import Request

from ..application.security.sessions import (
    LoginSessionService,
    LogoutService,
    RefreshSessionService,
)
from ..application.use_cases.generate_forecast import GenerateForecastUseCase
from ..application.use_cases.generate_market_forecast import GenerateMarketForecastUseCase
from ..core.config import get_settings
from ..infrastructure.market_data.twelve_data_provider import TwelveDataMarketDataProvider
from ..infrastructure.ml.simple_forecaster import SimpleMovingAverageForecaster
from ..infrastructure.repositories.in_memory_forecast_repository import InMemoryForecastRepository


def get_login_session_service(request: Request) -> LoginSessionService:
    return request.app.state.login_session_service  # type: ignore[no-any-return]


def get_refresh_session_service(request: Request) -> RefreshSessionService:
    return request.app.state.refresh_session_service  # type: ignore[no-any-return]


def get_logout_service(request: Request) -> LogoutService:
    return request.app.state.logout_service  # type: ignore[no-any-return]


@lru_cache
def get_generate_forecast_use_case() -> GenerateForecastUseCase:
    forecaster = SimpleMovingAverageForecaster()
    repository = InMemoryForecastRepository()
    return GenerateForecastUseCase(service=forecaster, repository=repository)


@lru_cache
def get_generate_market_forecast_use_case() -> GenerateMarketForecastUseCase:
    settings = get_settings()
    if not settings.twelve_data_api_key:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market data API key is not configured.",
        )

    provider = TwelveDataMarketDataProvider(
        api_key=settings.twelve_data_api_key,
        base_url=settings.twelve_data_base_url,
        timeout_seconds=settings.market_data_timeout_seconds,
    )
    forecaster = SimpleMovingAverageForecaster()
    repository = InMemoryForecastRepository()
    return GenerateMarketForecastUseCase(
        provider=provider,
        service=forecaster,
        repository=repository,
    )
