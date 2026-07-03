from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_generate_forecast() -> None:
    payload = {
        "symbol": "MSFT",
        "historical_values": [100.0, 101.2, 102.5, 103.3],
        "horizon": 3,
    }

    response = client.post("/api/v1/forecast", json=payload)
    body = response.json()

    assert response.status_code == 200
    assert body["symbol"] == "MSFT"
    assert body["horizon"] == 3
    assert len(body["points"]) == 3


def test_generate_forecast_validation_error() -> None:
    payload = {
        "symbol": "MSFT",
        "historical_values": [],
        "horizon": 3,
    }

    response = client.post("/api/v1/forecast", json=payload)

    assert response.status_code == 422
