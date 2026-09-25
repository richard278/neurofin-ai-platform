import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_market_data_settings_defaults() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]  # BaseSettings accepts _env_file

    assert settings.twelve_data_api_key is None
    assert settings.twelve_data_base_url == "https://api.twelvedata.com"
    assert settings.market_data_timeout_seconds == 5.0


def test_market_data_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(market_data_timeout_seconds=0, _env_file=None)  # type: ignore[call-arg]  # BaseSettings accepts _env_file
