from ...domain.entities.forecast import ForecastInput, ForecastResult
from ...domain.repositories.forecast_repository import ForecastRepository
from ...domain.services.forecast_service import ForecastService
from ...domain.services.market_data_provider import (
    MarketDataInvalidResponseError,
    MarketDataProvider,
)


class GenerateMarketForecastUseCase:
    def __init__(
        self,
        provider: MarketDataProvider,
        service: ForecastService,
        repository: ForecastRepository,
    ) -> None:
        self._provider = provider
        self._service = service
        self._repository = repository

    async def execute(self, symbol: str, horizon: int, observations: int) -> ForecastResult:
        normalized_symbol = symbol.strip().upper()
        closes = await self._provider.get_daily_closes(normalized_symbol, observations)
        if len(closes) < 2:
            raise MarketDataInvalidResponseError(
                "Market data provider returned insufficient historical observations."
            )

        result = self._service.predict(
            ForecastInput(
                symbol=normalized_symbol,
                historical_values=closes,
                horizon=horizon,
            )
        )
        self._repository.save(result)
        return result
