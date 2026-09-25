from abc import ABC, abstractmethod


class MarketDataProviderError(RuntimeError):
    pass


class MarketSymbolNotFoundError(MarketDataProviderError):
    pass


class MarketDataRateLimitError(MarketDataProviderError):
    pass


class MarketDataUnavailableError(MarketDataProviderError):
    pass


class MarketDataInvalidResponseError(MarketDataProviderError):
    pass


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_daily_closes(self, symbol: str, observations: int) -> list[float]:
        raise NotImplementedError
