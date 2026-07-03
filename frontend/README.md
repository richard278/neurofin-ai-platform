# NeuroFin Frontend

Frontend dashboard for NeuroFin AI Platform.

## Week 1 scope

- Scaffold React + Vite + TypeScript
- Build the base layout and routing
- Define theme tokens and global styles
- Add a typed API client for backend integration

## Stack

- React
- Vite
- TypeScript
- React Router
- TanStack Query

## Getting started

```bash
npm install
npm run dev
```

## Environment

Copy `.env.example` to `.env` and adjust the API base URL if needed:

```text
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Project structure

```text
src/
├── api/
├── components/
├── hooks/
├── layouts/
├── pages/
├── routes/
└── styles/
```

## Notes

- The backend health endpoint is wired into the dashboard shell.
- The forecast client is scaffolded for the next sprint.
- The UI is intentionally premium and minimal to support portfolio presentation.
