import asyncio

import typer

app = typer.Typer(help="Workspace operations")


@app.command("list")
def list_workspaces():
    """List all workspaces."""
    from sqlalchemy import select

    from app.infra.db.engine import db_session
    from app.infra.db.models import Workspace

    async def run():
        async with db_session() as s:
            for ws in await s.scalars(select(Workspace)):
                typer.echo(f"{ws.id}  {ws.slug:24}  {ws.name}")

    asyncio.run(run())
