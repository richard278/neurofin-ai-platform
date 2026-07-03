"""
This module implements an in-memory repository for storing and retrieving forecast results.
"""
from ...domain.entities.forecast import ForecastResult
from ...domain.repositories.forecast_repository import ForecastRepository


class InMemoryForecastRepository(ForecastRepository):
    """ This class provides an in-memory implementation of the `ForecastRepository` interface.
    It allows saving and retrieving forecast results based on their associated symbols."""
    def __init__(self) -> None:
        self._data: dict[str, ForecastResult] = {}

    def save(self, result: ForecastResult) -> None:
        self._data[result.symbol] = result

    def latest_for_symbol(self, symbol: str) -> ForecastResult | None:
        return self._data.get(symbol)
