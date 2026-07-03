# NeuroFin Forecast

Financial forecasting platform with a Clean Architecture backend built in FastAPI.

## Core stack

- FastAPI (REST API)
- Machine Learning / Econometrics
- Python
- Docker-ready backend
- PostgreSQL and Redis ready integrations
- Azure ecosystem compatible

## Repository layout

```text
neurofin-forecast/
├── backend/
│   ├── app/
│   │   ├── application/
│   │   ├── core/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   ├── presentation/
│   │   └── main.py
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
└── README.md
```

See backend setup and run instructions in [backend/README.md](backend/README.md).



neurofin-ai-platform
│
├── app
├── tests
├── docs
│   ├── 00-vision.md
│   ├── 01-architecture.md
│   ├── 02-roadmap.md
│   ├── 03-domain-model.md
│   ├── 04-api-design.md
│   ├── 05-machine-learning.md
│   ├── 06-azure-integration.md
│   ├── 07-deployment.md
│   ├── adr
│   │     ├── ADR-001-clean-architecture.md
│   │     ├── ADR-002-fastapi.md
│   │     ├── ADR-003-machine-learning.md
│   │     └── ADR-004-azure-ai.md
│   └── diagrams
│         ├── architecture.png
│         ├── data-flow.png
│         └── deployment.png
│
├── notebooks
├── README.md
└── pyproject.toml