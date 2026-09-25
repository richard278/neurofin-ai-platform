import math
from typing import Any

import httpx

from ...domain.services.market_data_provider import (
    MarketDataInvalidResponseError,
    MarketDataProvider,
    MarketDataRateLimitError,
    MarketDataUnavailableError,
    MarketSymbolNotFoundError,
)


class TwelveDataMarketDataProvider(MarketDataProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.twelvedata.com",
        timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Twelve Data API key must not be empty.")
        if timeout_seconds <= 0:
            raise ValueError("Market data timeout must be greater than zero.")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client

    async def get_daily_closes(self, symbol: str, observations: int) -> list[float]:
        try:
            response = await self._get(
                "/time_series",
                params={
                    "symbol": symbol,
                    "interval": "1day",
                    "outputsize": observations,
                },
                headers={"Authorization": f"apikey {self._api_key}"},
            )
        except httpx.TimeoutException as error:
            raise MarketDataUnavailableError("Market data provider timed out.") from error
        except httpx.RequestError as error:
            raise MarketDataUnavailableError("Market data provider is unavailable.") from error

        self._raise_for_provider_status(response)
        payload = self._decode_payload(response)
        self._raise_for_payload_error(payload)

        values = payload.get("values")
        if not isinstance(values, list) or not values:
            raise MarketDataInvalidResponseError(
                "Market data provider returned no historical values."
            )

        closes: list[float] = []
        for item in reversed(values):
            if not isinstance(item, dict) or "close" not in item:
                raise MarketDataInvalidResponseError(
                    "Market data provider returned an invalid time-series item."
                )
            try:
                close_val = float(item["close"])
            except (TypeError, ValueError) as error:
                raise MarketDataInvalidResponseError(
                    "Market data provider returned a non-numeric closing price."
                ) from error
            if not math.isfinite(close_val):
                raise MarketDataInvalidResponseError(
                    "Market data provider returned a non-finite closing price."
                )
            closes.append(close_val)

        return closes

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, str | int],
        headers: dict[str, str],
    ) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(path, params=params, headers=headers)

        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            return await client.get(path, params=params, headers=headers)

    @staticmethod
    def _decode_payload(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as error:
            raise MarketDataInvalidResponseError(
                "Market data provider returned malformed JSON."
            ) from error

        if not isinstance(payload, dict):
            raise MarketDataInvalidResponseError(
                "Market data provider returned an unexpected payload."
            )
        return payload

    @staticmethod
    def _raise_for_provider_status(response: httpx.Response) -> None:
        if response.status_code == 404:
            raise MarketSymbolNotFoundError("Requested market symbol was not found.")
        if response.status_code == 429:
            raise MarketDataRateLimitError("Market data provider rate limit reached.")
        if response.status_code >= 500:
            raise MarketDataUnavailableError("Market data provider is unavailable.")
        if response.status_code >= 400:
            raise MarketDataInvalidResponseError(
                f"Market data provider rejected the request with HTTP {response.status_code}."
            )

    @staticmethod
    def _raise_for_payload_error(payload: dict[str, Any]) -> None:
        if payload.get("status") != "error":
            return

        code = payload.get("code")
        if code == 404:
            raise MarketSymbolNotFoundError("Requested market symbol was not found.")
        if code == 429:
            raise MarketDataRateLimitError("Market data provider rate limit reached.")
        if isinstance(code, int) and code >= 500:
            raise MarketDataUnavailableError("Market data provider is unavailable.")
        raise MarketDataInvalidResponseError("Market data provider returned an error response.")
