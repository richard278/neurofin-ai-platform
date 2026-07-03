from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastInput:
    symbol: str
    historical_values: list[float]
    horizon: int


@dataclass(frozen=True)
class ForecastPoint:
    step: int
    value: float


@dataclass(frozen=True)
class ForecastResult:
    symbol: str
    horizon: int
    points: list[ForecastPoint]
