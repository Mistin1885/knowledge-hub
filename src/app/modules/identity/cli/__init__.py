import asyncio

import typer

app = typer.Typer(help="Identity operations")


@app.command("create-user")
def create_user(
    email: str,
    name: str,
    password: str = typer.Option(..., prompt=True, hide_input=True),
    admin: bool = typer.Option(False, "--admin"),
):
    """Create a user directly (bypasses registration_open)."""
    from pwdlib import PasswordHash

    from app.infra.db.engine import db_session
    from app.modules.identity.infra import repo

    async def run():
        async with db_session() as s:
            if await repo.get_user_by_email(s, email):
                typer.echo("User already exists", err=True)
                raise typer.Exit(1)
            user = await repo.create_user(
                s, email, name, PasswordHash.recommended().hash(password), admin
            )
            typer.echo(f"Created {user.email} ({user.id})")

    asyncio.run(run())
