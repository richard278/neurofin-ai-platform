# NeuroFin AI Platform

AI-powered financial forecasting platform built with **FastAPI**, **Clean Architecture** and **Machine Learning foundations**.

This repository contains the initial MVP backend for NeuroFin AI Platform. The current functional module is focused on financial forecasting through a REST API.

## MVP status

Current version: `v0.1.0-mvp`

Validated locally:

- FastAPI application running successfully.
- Swagger UI available at `/docs`.
- Health endpoint validated.
- Forecast endpoint validated.
- Automated tests passing.
- Stable Python dependency file defined with `requirements.txt`.

## Core stack

- Python 3.11
- FastAPI
- Pydantic
- NumPy
- Pandas
- SciPy
- scikit-learn
- Pytest
- Clean Architecture
- Azure-compatible roadmap

## Repository layout


```text
neurofin-ai-platform/
├── backend/
│   ├── app/
│   │   ├── application/
│   │   ├── core/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   ├── presentation/
│   │   └── main.py
│   ├── docs/
│   │   ├── adr/
│   │   ├── 00-vision.md
│   │   ├── 01-architecture.md
│   │   ├── 02-roadmap.md
│   │   ├── 03-domain-model.md
│   │   ├── 04-api-design.md
│   │   ├── 05-artificial-intelligence-strategy.md
│   │   ├── 06-azure-integration.md
│   │   └── 07-deployment.md
│   ├── tests/
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── .env.example
│   └── README.md
├── frontend/
│   └── README.md
├── .gitignore
└── README.md
```

## Backend setup

Go to the backend directory:

```bash
cd backend
```

Create and activate a virtual environment on Windows CMD:

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Validate dependency consistency:

```bash
python -m pip check
```

Run tests:

```bash
python -m pytest
```

Expected result:

```text
> 170 passed
```

## Run the API

From the `backend` directory:

```bash
uvicorn app.main:app --reload
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Available endpoints

```text
GET  /api/v1/health
POST /api/v1/forecast
POST /api/v1/forecast/market-data
```

Example `POST /api/v1/forecast` request:

```json
{
  "symbol": "MSFT",
  "historical_values": [100.0, 101.2, 102.5, 103.3],
  "horizon": 3
}
```

Example response:

```json
{
  "symbol": "MSFT",
  "horizon": 3,
  "points": [
    {
      "step": 1,
      "value": 101.75
    },
    {
      "step": 2,
      "value": 101.75
    },
    {
      "step": 3,
      "value": 101.75
    }
  ]
}
```

Example `POST /api/v1/forecast/market-data` request:
*(Requires `TWELVE_DATA_API_KEY` to be set in `.env`)*

```json
{
  "symbol": "MSFT",
  "horizon": 2,
  "observations": 3
}
```

Example response (uses a simple moving average on historical market data, illustrative):

```json
{
  "symbol": "MSFT",
  "horizon": 2,
  "points": [
    {
      "step": 1,
      "value": 101.75
    },
    {
      "step": 2,
      "value": 101.75
    }
  ]
}
```

## Architecture approach

The backend follows a Clean Architecture-oriented structure:

- `domain`: business entities, service contracts and domain abstractions.
- `application`: use cases.
- `infrastructure`: concrete implementations, including the initial ML forecaster.
- `presentation`: API routes, schemas and dependency wiring.

## Strategic roadmap

The current MVP is intentionally focused and portfolio-ready. It includes core foundations for authentication, persistent storage, integration with external market data (Twelve Data), and an existing frontend client for dashboards and forecast visualization.

To use the market data forecasting endpoint, set your API key in the `.env` file (do not use real keys in public repositories):
```env
TWELVE_DATA_API_KEY=your_test_key_here
```

Future evolution may include:
- More advanced forecasting models (currently uses SMA).
- Azure deployment.
- SaaS-oriented multi-tenant architecture.

## Documentation

Technical documentation is available in:

```text
backend/docs/
```

Architecture decisions are available in:

```text
backend/docs/adr/
```

## Notes

This project is educational and portfolio-oriented. Forecast results are not financial advice.
