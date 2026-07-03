import os

os.environ["KM_DATABASE_URL"] = "postgresql+asyncpg://km@localhost:5433/km_test"

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
async def clean_db(migrated_db):
    yield
    from app.infra.db.engine import engine

    async with engine.begin() as conn:
        tables = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename != 'alembic_version'"
            )
        )
        names = ", ".join(f'"{t[0]}"' for t in tables)
        if names:
            await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client():
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register_and_login(
    client: httpx.AsyncClient, email: str, name: str = "User", password: str = "password123"
) -> dict:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "name": name, "password": password}
    )
    assert resp.status_code == 201, resp.text
    user = resp.json()
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return user


@pytest.fixture
async def alice(client):
    return await register_and_login(client, "alice@test.com", "Alice")


async def make_workspace(client, name="Team") -> dict:
    resp = await client.post("/api/v1/workspaces", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()
