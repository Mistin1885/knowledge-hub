# --- frontend build ---
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- backend ---
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /srv/km

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini README.md ./
RUN uv sync --frozen --no-dev

COPY --from=frontend /build/dist ./frontend/dist

ENV KM_UPLOADS_DIR=/srv/km/data/uploads
EXPOSE 8000
CMD ["sh", "-c", "uv run alembic upgrade head && uv run km serve --host 0.0.0.0 --port 8000"]
