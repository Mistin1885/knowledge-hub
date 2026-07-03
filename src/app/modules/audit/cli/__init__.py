import asyncio
import uuid

import typer

app = typer.Typer(help="Audit log operations")


@app.command("tail")
def tail(workspace_id: str, limit: int = 20):
    """Show recent audit entries for a workspace."""
    from app.infra.db.engine import db_session
    from app.modules.audit.infra import repo

    async def run():
        async with db_session() as s:
            for e in await repo.list_for_workspace(s, uuid.UUID(workspace_id), limit=limit):
                typer.echo(f"{e.created_at:%Y-%m-%d %H:%M} {e.action:24} {e.target_title or e.target_id}")

    asyncio.run(run())
