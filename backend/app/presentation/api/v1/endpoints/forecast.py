from fastapi import APIRouter, Depends, HTTPException, status

from .....application.use_cases.generate_forecast import GenerateForecastUseCase
from .....domain.entities.forecast import ForecastInput
from ..schemas.forecast import ForecastRequest, ForecastResponse
from ....dependencies import get_generate_forecast_use_case

router = APIRouter()


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

    return ForecastResponse(
        symbol=result.symbol,
        horizon=result.horizon,
        points=[{"step": point.step, "value": point.value} for point in result.points],
    )
