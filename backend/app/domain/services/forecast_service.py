from abc import ABC, abstractmethod

from ..entities.forecast import ForecastInput, ForecastResult


class ForecastService(ABC):
    @abstractmethod
    def predict(self, data: ForecastInput) -> ForecastResult:
        raise NotImplementedError
