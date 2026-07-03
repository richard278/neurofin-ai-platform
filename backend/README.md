# NeuroFin Forecast Backend

Professional FastAPI backend using **Clean Architecture**.

## Architecture

The project is organized in concentric layers:

- **Domain**: Business rules and contracts (framework-agnostic).
- **Application**: Use cases and orchestration.
- **Infrastructure**: External services and technical implementations.
- **Presentation**: FastAPI routes, schemas and dependency wiring.

## Project Structure

```text
backend/
├── app/
│   ├── application/
│   ├── core/
│   ├── domain/
│   ├── infrastructure/
│   ├── presentation/
│   └── main.py
├── tests/
├── pyproject.toml
└── .env.example
```

## Quick Start

1. Create and activate your virtual environment.
2. Install dependencies:

   ```bash
   pip install -e .[dev]
   ```

3. Copy environment variables:

   ```bash
   copy .env.example .env
   ```

4. Run the API:

   ```bash
   uvicorn app.main:app --reload
   ```

5. Open docs:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Endpoints

- `GET /api/v1/health`
- `POST /api/v1/forecast`

## Testing

```bash
pytest -q
```
