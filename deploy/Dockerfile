# --- frontend build ---
FROM node:20-slim AS frontend
WORKDIR /build
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci
COPY src/frontend/ ./
RUN npm run build

# --- backend ---
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /srv/knowledge-hub

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/app ./src/app
COPY alembic ./alembic
COPY alembic.ini README.md ./
RUN uv sync --frozen --no-dev

COPY --from=frontend /build/dist ./src/frontend/dist

ENV KM_UPLOADS_DIR=/srv/knowledge-hub/data/uploads \
    KM_FRONTEND_DIST=/srv/knowledge-hub/src/frontend/dist
EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && uv run km serve --host 0.0.0.0 --port 8000"]
