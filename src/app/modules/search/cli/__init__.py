import asyncio
import uuid

import typer

app = typer.Typer(help="Search index operations")


@app.command("reindex")
def reindex(workspace_id: str):
    """Rebuild chunks + embeddings for every page in a workspace."""
    from app.infra.db.engine import db_session
    from app.modules.search.services import indexer

    async def run():
        async with db_session() as s:
            n = await indexer.reindex_workspace(s, uuid.UUID(workspace_id))
            typer.echo(f"Reindexed {n} pages")

    asyncio.run(run())
