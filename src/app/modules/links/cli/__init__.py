import asyncio
import uuid

import typer

app = typer.Typer(help="Link graph operations")


@app.command("reparse")
def reparse(workspace_id: str):
    """Re-run link extraction for every page in a workspace."""
    from sqlalchemy import select

    from app.infra.db.engine import db_session
    from app.infra.db.models import Page
    from app.modules.links.domain import parser
    from app.modules.links.infra import repo

    async def run():
        async with db_session() as s:
            pages = list(
                await s.scalars(select(Page).where(Page.workspace_id == uuid.UUID(workspace_id)))
            )
            for page in pages:
                doc = parser.parse_document(page.content_md)
                await repo.replace_links(s, page, doc.links)
            typer.echo(f"Reparsed links for {len(pages)} pages")

    asyncio.run(run())
