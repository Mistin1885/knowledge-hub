import asyncio
import uuid

import typer

app = typer.Typer(help="Collaboration doc operations")


@app.command("show-md")
def show_md(page_id: str):
    """Render the persisted Yjs doc of a page as markdown (debugging)."""
    from pycrdt import Doc, XmlFragment

    from app.infra.db.engine import db_session
    from app.modules.collab.domain.y_markdown import fragment_to_md
    from app.modules.collab.infra import ypersistence

    async def run():
        async with db_session() as s:
            state = await ypersistence.load_state(s, uuid.UUID(page_id))
            if state is None:
                typer.echo("No Yjs state persisted for this page")
                return
            doc = Doc()
            doc.apply_update(state)
            typer.echo(fragment_to_md(doc.get("default", type=XmlFragment)))

    asyncio.run(run())
