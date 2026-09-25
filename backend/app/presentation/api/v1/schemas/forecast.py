from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class ForecastRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20, description="Ticker or asset identifier")
    historical_values: list[float] = Field(min_length=1, description="Observed historical values")
    horizon: int = Field(default=12, ge=1, le=120, description="Number of future periods")

MarketSymbol = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20, pattern=r"^[^\s]+$"),
]

class MarketForecastRequest(BaseModel):
    symbol: MarketSymbol
    horizon: int = Field(default=12, ge=1, le=120, description="Number of future periods")
    observations: int = Field(
        default=30,
        ge=2,
        le=100,
        description="Number of daily market observations to retrieve",
    )

class ForecastPointResponse(BaseModel):
    step: int
    value: float

class ForecastResponse(BaseModel):
    symbol: str
    horizon: int
    points: list[ForecastPointResponse]
