import asyncio

import typer

app = typer.Typer(help="Page operations")


@app.command("export")
def export(workspace_slug: str, out_dir: str = "output/export"):
    """Export all pages of a workspace as markdown files (Obsidian-compatible vault)."""
    from pathlib import Path

    from sqlalchemy import select

    from app.infra.db.engine import db_session
    from app.infra.db.models import Page, Workspace
    from app.modules.pages.infra import repo
    from app.shared.utils import slugify

    async def run():
        async with db_session() as s:
            ws = await s.scalar(select(Workspace).where(Workspace.slug == workspace_slug))
            if ws is None:
                typer.echo("Workspace not found", err=True)
                raise typer.Exit(1)
            base = Path(out_dir) / ws.slug
            base.mkdir(parents=True, exist_ok=True)
            pages = list(await s.scalars(select(Page).where(Page.workspace_id == ws.id)))
            for page in pages:
                tags = await repo.get_page_tags(s, page.id)
                meta = await repo.get_page_metadata(s, page.id)
                fm_lines = ["---", f"title: {page.title}", f"status: {page.status}"]
                if tags:
                    fm_lines.append("tags: [" + ", ".join(tags) + "]")
                fm_lines += [f"{k}: {v}" for k, v in meta.items()]
                fm_lines.append("---")
                (base / f"{slugify(page.title)}-{str(page.id)[:8]}.md").write_text(
                    "\n".join(fm_lines) + "\n\n" + page.content_md
                )
            typer.echo(f"Exported {len(pages)} pages to {base}")

    asyncio.run(run())
