"""Application dependency composition for forecast use cases."""
from functools import lru_cache

from ..application.use_cases.generate_forecast import GenerateForecastUseCase
from ..application.use_cases.generate_market_forecast import GenerateMarketForecastUseCase
from ..core.config import get_settings
from ..infrastructure.market_data.twelve_data_provider import TwelveDataMarketDataProvider
from ..infrastructure.ml.simple_forecaster import SimpleMovingAverageForecaster
from ..infrastructure.repositories.in_memory_forecast_repository import InMemoryForecastRepository


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
