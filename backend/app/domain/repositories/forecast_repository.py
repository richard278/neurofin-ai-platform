from abc import ABC, abstractmethod

from ..entities.forecast import ForecastResult


class ForecastRepository(ABC):
    @abstractmethod
    def save(self, result: ForecastResult) -> None:
        raise NotImplementedError

    @abstractmethod
    def latest_for_symbol(self, symbol: str) -> ForecastResult | None:
        raise NotImplementedError
