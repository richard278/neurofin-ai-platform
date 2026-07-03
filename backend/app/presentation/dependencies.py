""" 
This module defines the dependencies for the application layer, 
specifically the use case for generating forecasts. 
It uses the `lru_cache` decorator to cache the instance of `GenerateForecastUseCase`, 
ensuring that the same instance is reused across multiple calls, 
which can improve performance and resource utilization.
"""
from functools import lru_cache

from ..application.use_cases.generate_forecast import GenerateForecastUseCase
from ..infrastructure.ml.simple_forecaster import SimpleMovingAverageForecaster
from ..infrastructure.repositories.in_memory_forecast_repository import InMemoryForecastRepository


@lru_cache
def get_generate_forecast_use_case() -> GenerateForecastUseCase:
    """
    this function returns a cached instance of the `GenerateForecastUseCase`, 
    which is responsible for generating forecasts. 
    It initializes the necessary components, including the forecaster and repository, 
    and returns the use case instance.
    """
    forecaster = SimpleMovingAverageForecaster()
    repository = InMemoryForecastRepository()
    return GenerateForecastUseCase(service=forecaster, repository=repository)
