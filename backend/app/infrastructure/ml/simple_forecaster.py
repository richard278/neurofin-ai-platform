"""
This module implements a simple moving average forecaster as a baseline forecasting service.
It uses the arithmetic mean of historical values to project future values for a specified horizon.
"""
from ...domain.entities.forecast import ForecastInput, ForecastPoint, ForecastResult
from ...domain.services.forecast_service import ForecastService


class SimpleMovingAverageForecaster(ForecastService):
    """
    Baseline forecasting service.
    Uses the arithmetic mean of historical values and projects it for each future step.
    This can be replaced by ARIMA, Prophet, or deep-learning models in the same contract.
    """

    def predict(self, data: ForecastInput) -> ForecastResult:
        if not data.historical_values:
            raise ValueError("historical_values cannot be empty")

        mean_value = sum(data.historical_values) / len(data.historical_values)
        points = [ForecastPoint(step=i + 1, value=round(mean_value, 4)) for i in range(data.horizon)]
        return ForecastResult(symbol=data.symbol, horizon=data.horizon, points=points)
