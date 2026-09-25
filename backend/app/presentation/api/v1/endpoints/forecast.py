from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from .....application.use_cases.generate_forecast import GenerateForecastUseCase
from .....application.use_cases.generate_market_forecast import GenerateMarketForecastUseCase
from .....domain.entities.forecast import ForecastInput, ForecastResult
from .....domain.services.market_data_provider import (
    MarketDataInvalidResponseError,
    MarketDataRateLimitError,
    MarketDataUnavailableError,
    MarketSymbolNotFoundError,
)
from ....dependencies import (
    get_generate_forecast_use_case,
    get_generate_market_forecast_use_case,
)
from ..schemas.forecast import (
    ForecastPointResponse,
    ForecastRequest,
    ForecastResponse,
    MarketForecastRequest,
)

router = APIRouter()


def _to_response(result: ForecastResult) -> ForecastResponse:
    return ForecastResponse(
        symbol=result.symbol,
        horizon=result.horizon,
        points=[
            ForecastPointResponse(step=point.step, value=point.value)
            for point in result.points
        ],
    )


@router.post(
    "/forecast",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a financial forecast",
)
def generate_forecast(
    payload: ForecastRequest,
    use_case: GenerateForecastUseCase = Depends(get_generate_forecast_use_case),
) -> ForecastResponse:
    try:
        result = use_case.execute(
            ForecastInput(
                symbol=payload.symbol.upper(),
                historical_values=payload.historical_values,
                horizon=payload.horizon,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return _to_response(result)


@router.post(
    "/forecast/market-data",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a forecast from external market data",
)
async def generate_market_forecast(
    payload: MarketForecastRequest,
    use_case: Annotated[
        GenerateMarketForecastUseCase,
        Depends(get_generate_market_forecast_use_case),
    ],
) -> ForecastResponse:
    try:
        result = await use_case.execute(
            symbol=payload.symbol,
            horizon=payload.horizon,
            observations=payload.observations,
        )
    except MarketSymbolNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error
    except (MarketDataRateLimitError, MarketDataUnavailableError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except MarketDataInvalidResponseError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    return _to_response(result)
