import httpx
import pytest

from app.domain.services.market_data_provider import (
    MarketDataInvalidResponseError,
    MarketDataRateLimitError,
    MarketDataUnavailableError,
    MarketSymbolNotFoundError,
)
from app.infrastructure.market_data.twelve_data_provider import TwelveDataMarketDataProvider


def _provider(handler: httpx.MockTransport) -> tuple[TwelveDataMarketDataProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(base_url="https://api.twelvedata.com", transport=handler)
    return TwelveDataMarketDataProvider(api_key="test-key", client=client), client


@pytest.mark.asyncio
async def test_twelve_data_provider_returns_closes_in_chronological_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "apikey test-key"
        assert request.url.params["symbol"] == "MSFT"
        assert request.url.params["interval"] == "1day"
        assert request.url.params["outputsize"] == "3"
        return httpx.Response(
            200,
            json={
                "values": [
                    {"datetime": "2026-09-23", "close": "103.0"},
                    {"datetime": "2026-09-22", "close": "102.0"},
                    {"datetime": "2026-09-21", "close": "101.0"},
                ]
            },
        )

    provider, client = _provider(httpx.MockTransport(handler))
    try:
        closes = await provider.get_daily_closes("MSFT", 3)
    finally:
        await client.aclose()

    assert closes == [101.0, 102.0, 103.0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (404, MarketSymbolNotFoundError),
        (429, MarketDataRateLimitError),
        (500, MarketDataUnavailableError),
    ],
)
async def test_twelve_data_provider_maps_http_errors(
    status_code: int, error_type: type[Exception]
) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(status_code, json={}))
    provider, client = _provider(transport)
    try:
        with pytest.raises(error_type):
            await provider.get_daily_closes("MSFT", 3)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_twelve_data_provider_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    provider, client = _provider(httpx.MockTransport(handler))
    try:
        with pytest.raises(MarketDataUnavailableError):
            await provider.get_daily_closes("MSFT", 3)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_twelve_data_provider_rejects_malformed_payload() -> None:
    provider, client = _provider(
        httpx.MockTransport(lambda _request: httpx.Response(200, content=b"not-json"))
    )
    try:
        with pytest.raises(MarketDataInvalidResponseError):
            await provider.get_daily_closes("MSFT", 3)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_twelve_data_provider_rejects_empty_values() -> None:
    provider, client = _provider(
        httpx.MockTransport(lambda _request: httpx.Response(200, json={"values": []}))
    )
    try:
        with pytest.raises(MarketDataInvalidResponseError):
            await provider.get_daily_closes("MSFT", 3)
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_close", ["NaN", "Infinity", "-Infinity"])
async def test_twelve_data_provider_rejects_non_finite_closes(invalid_close: str) -> None:
    provider, client = _provider(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"values": [{"datetime": "2026-09-23", "close": invalid_close}]}
            )
        )
    )
    try:
        with pytest.raises(MarketDataInvalidResponseError):
            await provider.get_daily_closes("MSFT", 1)
    finally:
        await client.aclose()
