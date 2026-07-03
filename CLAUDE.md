# CLAUDE.md

Guidance for Claude/Codex agents working in this repository.

## Project

- Name: **Knowledge Hub** (`knowledge-hub`)
- Purpose: self-hosted collaborative knowledge base with Obsidian-style wikilinks, Notion-style realtime collaboration, RBAC, comments, attachments, search, and MCP access.
- Backend: Python 3.12, FastAPI, SQLAlchemy async, PostgreSQL + pgvector, uv.
- Frontend: React/Vite/TypeScript in `src/frontend/`.
- The CLI entry point remains `km` and environment variables still use the `KM_` prefix for backward compatibility.

## Layout

- `src/app/` — backend application, modules, DB, API routers, MCP server.
- `src/frontend/` — React SPA.
- `deploy/Dockerfile` and `deploy/docker-compose.yml` — container packaging/deployment.
- `data/` — local runtime data only; ignored by git.
  - `data/postgres/` stores PostgreSQL system/user data such as pages, folders, comments, users, workspaces, and indexes.
  - `data/uploads/` stores uploaded attachments.

## Common commands

```bash
uv sync
uv run alembic upgrade head
uv run km serve --reload
uv run pytest

cd src/frontend
npm install
npm run dev
npm run build
```

Docker compose from repo root:

```bash
cp .env.example .env
mkdir -p data/postgres data/uploads
docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
```

## Hygiene rules

- Do not commit caches, virtualenvs, build output, `node_modules`, `.env`, or `data/`.
- Keep `.gitignore` and `.dockerignore` aligned when adding generated/runtime paths.
- Docker build context is the repo root; deployment files live under `deploy/`.
- If changing frontend location/build output, update `KM_FRONTEND_DIST`, `src/app/shared/config/settings.py`, Dockerfile, and README together.
