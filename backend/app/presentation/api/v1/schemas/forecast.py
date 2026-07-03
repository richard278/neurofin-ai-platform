from pydantic import BaseModel, Field


class ForecastRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20, description="Ticker or asset identifier")
    historical_values: list[float] = Field(min_length=1, description="Observed historical values")
    horizon: int = Field(default=12, ge=1, le=120, description="Number of future periods")


class ForecastPointResponse(BaseModel):
    step: int
    value: float


class ForecastResponse(BaseModel):
    symbol: str
    horizon: int
    points: list[ForecastPointResponse]
