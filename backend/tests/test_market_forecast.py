from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.application.use_cases.generate_market_forecast import GenerateMarketForecastUseCase
from app.core.config import Settings
from app.domain.services.market_data_provider import MarketDataProvider
from app.infrastructure.ml.simple_forecaster import SimpleMovingAverageForecaster
from app.infrastructure.repositories.in_memory_forecast_repository import InMemoryForecastRepository
from app.main import app
from app.presentation.api.v1.schemas.forecast import MarketForecastRequest
from app.presentation.dependencies import get_generate_market_forecast_use_case


class FakeMarketDataProvider(MarketDataProvider):
    def __init__(self, closes: list[float]) -> None:
        self.closes = closes
        self.calls: list[tuple[str, int]] = []

    async def get_daily_closes(self, symbol: str, observations: int) -> list[float]:
        self.calls.append((symbol, observations))
        return self.closes


@pytest.mark.asyncio
async def test_generate_market_forecast_uses_provider_and_existing_forecaster() -> None:
    provider = FakeMarketDataProvider([100.0, 102.0, 104.0])
    repository = InMemoryForecastRepository()
    use_case = GenerateMarketForecastUseCase(
        provider=provider,
        service=SimpleMovingAverageForecaster(),
        repository=repository,
    )

    result = await use_case.execute(symbol="msft", horizon=2, observations=3)

    assert provider.calls == [("MSFT", 3)]
    assert result.symbol == "MSFT"
    assert [point.value for point in result.points] == [102.0, 102.0]
    assert repository.latest_for_symbol("MSFT") == result

def test_market_forecast_request_rejects_blank_symbol() -> None:
    with pytest.raises(ValidationError):
        MarketForecastRequest(
            symbol="   ",
            horizon=3,
            observations=30,
        )

def test_market_forecast_endpoint_is_deterministic_with_dependency_override() -> None:
    provider = FakeMarketDataProvider([10.0, 20.0, 30.0])
    use_case = GenerateMarketForecastUseCase(
        provider=provider,
        service=SimpleMovingAverageForecaster(),
        repository=InMemoryForecastRepository(),
    )
    app.dependency_overrides[get_generate_market_forecast_use_case] = lambda: use_case
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/forecast/market-data",
            json={"symbol": "MSFT", "horizon": 2, "observations": 3},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "MSFT",
        "horizon": 2,
        "points": [{"step": 1, "value": 20.0}, {"step": 2, "value": 20.0}],
    }

def test_market_forecast_endpoint_rejects_symbol_with_spaces() -> None:
    provider = FakeMarketDataProvider([10.0])
    use_case = GenerateMarketForecastUseCase(
        provider=provider,
        service=SimpleMovingAverageForecaster(),
        repository=InMemoryForecastRepository(),
    )
    app.dependency_overrides[get_generate_market_forecast_use_case] = lambda: use_case
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/forecast/market-data",
            json={"symbol": "AA PL", "horizon": 2, "observations": 3},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422

def test_market_forecast_endpoint_accepts_valid_symbol() -> None:
    # Just to verify a valid symbol is accepted by the validation
    # without depending on the override here, though it might fail fetching data if not mocked.
    # Actually, we can use the same dependency override as above.
    provider = FakeMarketDataProvider([10.0, 20.0, 30.0])
    use_case = GenerateMarketForecastUseCase(
        provider=provider,
        service=SimpleMovingAverageForecaster(),
        repository=InMemoryForecastRepository(),
    )
    app.dependency_overrides[get_generate_market_forecast_use_case] = lambda: use_case
    client = TestClient(app)

    try:
        response = client.post(
            "/api/v1/forecast/market-data",
            json={"symbol": "AAPL", "horizon": 2, "observations": 3},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"

def test_market_forecast_endpoint_returns_error_when_api_key_missing() -> None:
    get_generate_market_forecast_use_case.cache_clear()

    with patch("app.presentation.dependencies.get_settings") as mock_get_settings:
        mock_get_settings.return_value = Settings(twelve_data_api_key=None, _env_file=None)  # type: ignore[call-arg]
        client = TestClient(app)
        response = client.post(
            "/api/v1/forecast/market-data",
            json={"symbol": "AAPL", "horizon": 2, "observations": 3},
        )

    get_generate_market_forecast_use_case.cache_clear()

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()
