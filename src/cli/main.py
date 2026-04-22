"""Top-level CLI — ``jaa ...``.

Phase 0 exposes only introspection commands (``config``, ``db init``,
``version``). Later phases register their own sub-apps:

    scrape  — Phase 1
    filter  — Phase 2
    draft   — Phase 4
    bot     — Phase 5
    email   — Phase 6
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from pydantic import SecretStr
from rich import print as rprint
from rich.table import Table

from src import __version__
from src.config import get_settings, load_personal_info

app = typer.Typer(
    name="jaa",
    help="Job Application Automation — scaffolding CLI (Phase 0).",
    no_args_is_help=True,
    add_completion=False,
)

db_app = typer.Typer(name="db", help="Database / migrations.", no_args_is_help=True)
config_app = typer.Typer(name="config", help="Inspect configuration.", no_args_is_help=True)

app.add_typer(db_app)
app.add_typer(config_app)


@app.command()
def version() -> None:
    """Print the package version."""

    rprint(f"[bold]jaa[/bold] {__version__}")


@config_app.command("show")
def config_show() -> None:
    """Print the effective runtime settings (secrets masked)."""

    settings = get_settings()
    table = Table(title="Effective settings", show_lines=False)
    table.add_column("key", style="cyan", no_wrap=True)
    table.add_column("value")
    for key in sorted(settings.model_fields):
        raw = getattr(settings, key)
        if isinstance(raw, SecretStr):
            display = "***" if raw.get_secret_value() else "(unset)"
        else:
            display = repr(raw)
        table.add_row(key, display)
    rprint(table)


@config_app.command("personal")
def config_personal(
    path: Path | None = typer.Option(
        None,
        "--path",
        "-p",
        help="Override PERSONAL_INFO_PATH for this call.",
    ),
) -> None:
    """Validate and print the personal-info YAML profile."""

    target = path or get_settings().personal_info_path
    try:
        info = load_personal_info(target)
    except FileNotFoundError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from e

    rprint(f"[green]OK[/green] — loaded [bold]{info.full_name}[/bold] from {target}")
    rprint(f"  education:       {info.education.university} ({info.education.graduation_date})")
    rprint(f"  experiences:     {len(info.experiences)}")
    rprint(f"  projects:        {len(info.projects)}")
    rprint(f"  resume variants: {[v.name.value for v in info.resume_variants]}")


@db_app.command("upgrade")
def db_upgrade(
    revision: str = typer.Argument("head", help="Target revision."),
) -> None:
    """Run ``alembic upgrade <revision>``."""

    _run_alembic(["upgrade", revision])


@db_app.command("downgrade")
def db_downgrade(
    revision: str = typer.Argument("-1", help="Target revision."),
) -> None:
    """Run ``alembic downgrade <revision>``."""

    _run_alembic(["downgrade", revision])


@db_app.command("revision")
def db_revision(
    message: str = typer.Option(..., "--message", "-m"),
    autogenerate: bool = typer.Option(True, "--autogenerate/--no-autogenerate"),
) -> None:
    """Create a new Alembic revision."""

    cmd = ["revision"]
    if autogenerate:
        cmd.append("--autogenerate")
    cmd += ["-m", message]
    _run_alembic(cmd)


@db_app.command("current")
def db_current() -> None:
    """Show the current migration revision."""

    _run_alembic(["current"])


def _run_alembic(args: list[str]) -> None:
    try:
        result = subprocess.run([sys.executable, "-m", "alembic", *args], check=False)
    except FileNotFoundError as e:
        rprint("[red]alembic is not installed. Run `uv sync` first.[/red]")
        raise typer.Exit(code=1) from e
    raise typer.Exit(code=result.returncode)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
