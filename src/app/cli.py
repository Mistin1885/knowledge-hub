"""Operator CLI: `uv run km --help`."""

import asyncio

import typer

from app.modules.audit.cli import app as audit_cli
from app.modules.collab.cli import app as collab_cli
from app.modules.identity.cli import app as identity_cli
from app.modules.links.cli import app as links_cli
from app.modules.pages.cli import app as pages_cli
from app.modules.search.cli import app as search_cli
from app.modules.workspaces.cli import app as workspaces_cli

app = typer.Typer(help="Knowledge Map operations")
app.add_typer(identity_cli, name="identity")
app.add_typer(workspaces_cli, name="workspaces")
app.add_typer(pages_cli, name="pages")
app.add_typer(links_cli, name="links")
app.add_typer(search_cli, name="search")
app.add_typer(collab_cli, name="collab")
app.add_typer(audit_cli, name="audit")


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the web application."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@app.command()
def seed():
    """Create demo users and a starter workspace with interlinked pages."""
    from app.infra.db.engine import db_session
    from app.orchestration.seed_demo import seed as seed_fn

    async def run():
        async with db_session() as s:
            result = await seed_fn(s)
            typer.echo(result)

    asyncio.run(run())


@app.command("mcp-stdio")
def mcp_stdio():
    """Run the MCP server on stdio (for Claude Desktop / local agents).
    Requires KM_MCP_TOKEN env var with an API token."""
    from app.mcpserver.server import mcp

    mcp.run(transport="stdio")


if __name__ == "__main__":
    app()
