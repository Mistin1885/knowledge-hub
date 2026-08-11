import asyncio
import mimetypes
import uuid
from pathlib import Path

import typer

app = typer.Typer(help="Page operations")


@app.command("import-vault")
def import_vault(
    workspace_slug: str,
    vault_dir: Path,
    parent_id: uuid.UUID | None = None,
):
    """Import/update a filesystem Obsidian Vault with per-file progress."""
    from fastapi import UploadFile
    from sqlalchemy import select
    from starlette.datastructures import Headers

    from app.infra.db.engine import session_factory
    from app.infra.db.models import User, Workspace, WorkspaceMember
    from app.modules.pages.services import vault

    root = vault_dir.resolve()
    if not root.is_dir():
        typer.echo(f"Vault directory not found: {root}", err=True)
        raise typer.Exit(1)

    async def run():
        async with session_factory() as s:
            ws = await s.scalar(select(Workspace).where(Workspace.slug == workspace_slug))
            if ws is None:
                typer.echo("Workspace not found", err=True)
                raise typer.Exit(1)
            actor = await s.scalar(
                select(User)
                .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
                .where(WorkspaceMember.workspace_id == ws.id)
                .order_by(
                    (WorkspaceMember.role == "owner").desc(),
                    WorkspaceMember.joined_at,
                )
                .limit(1)
            )
            if actor is None:
                typer.echo("Workspace has no member who can perform the import", err=True)
                raise typer.Exit(1)
            workspace_id = ws.id
            actor_id = actor.id

            ignored_dirs = {".git", ".obsidian", ".trash"}
            paths = [
                path
                for path in root.rglob("*")
                if path.is_file() and not any(part.lower() in ignored_dirs for part in path.parts)
            ]
            paths.sort(
                key=lambda path: (
                    path.suffix.lower() in {".md", ".markdown"},
                    path.relative_to(root).as_posix().lower(),
                )
            )
            summary = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
            warnings: list[str] = []
            for index, path in enumerate(paths, start=1):
                relative_path = f"{root.name}/{path.relative_to(root).as_posix()}"
                media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                source = None
                try:
                    source = path.open("rb")
                    upload = UploadFile(
                        file=source,
                        filename=path.name,
                        headers=Headers({"content-type": media_type}),
                    )
                    action, _node, _folders, item_warnings = await vault.import_vault_item(
                        s,
                        actor,
                        workspace_id,
                        upload,
                        relative_path=relative_path,
                        base_parent_id=parent_id,
                    )
                    summary[action] += 1
                    warnings.extend(item_warnings)
                    await s.commit()
                except Exception as exc:  # continue the batch and report every failure
                    await s.rollback()
                    # Rollback expires ORM rows; reload the actor so the next
                    # item does not trigger async lazy-loading (MissingGreenlet).
                    actor = await s.get(User, actor_id)
                    if actor is None:
                        raise RuntimeError("Import actor no longer exists") from exc
                    summary["failed"] += 1
                    warnings.append(f"{relative_path}: {exc}")
                finally:
                    if source is not None and not source.closed:
                        source.close()
                if index == 1 or index % 25 == 0 or index == len(paths):
                    typer.echo(
                        f"[{index}/{len(paths)}] "
                        f"created={summary['created']}, updated={summary['updated']}, "
                        f"skipped={summary['skipped']}, failed={summary['failed']}"
                    )
            typer.echo(f"Import complete: {summary}")
            if warnings:
                typer.echo(f"Warnings ({len(warnings)}):", err=True)
                for warning in warnings[:100]:
                    typer.echo(f"- {warning}", err=True)
            if summary["failed"]:
                raise typer.Exit(1)

    asyncio.run(run())


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
