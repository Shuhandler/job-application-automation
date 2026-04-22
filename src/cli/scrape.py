"""``jaa scrape`` sub-app — invoke / run / validate scrapers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table

from src.config import get_settings, load_sources_config
from src.config.sources import SourcesConfig

scrape_app = typer.Typer(
    name="scrape",
    help="Run scrapers, Celery worker/beat, or validate sources config.",
    no_args_is_help=True,
)


@scrape_app.command("sources")
def sources_show(
    path: Path | None = typer.Option(
        None, "--path", "-p", help="Override SOURCES_CONFIG_PATH for this call."
    ),
) -> None:
    """Validate and summarize the sources YAML."""

    target = path or get_settings().sources_config_path
    try:
        cfg = load_sources_config(target)
    except FileNotFoundError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from e

    _print_sources_summary(cfg, target)


@scrape_app.command("once")
def scrape_once(
    path: Path | None = typer.Option(
        None, "--path", "-p", help="Override SOURCES_CONFIG_PATH for this call."
    ),
) -> None:
    """Run every enabled scraper serially, in-process (no broker needed)."""

    # Import lazily so `jaa` without the scraping extras still works.
    from src.tasks.scrape import run_all_sync

    if path is not None:
        import os

        os.environ["SOURCES_CONFIG_PATH"] = str(path)
        from src.config import settings as s

        s.get_settings.cache_clear()

    results = run_all_sync()
    if not results:
        rprint("[yellow]No enabled scrapers found in sources config.[/yellow]")
        return

    table = Table(title="Scrape results")
    for col in ("source", "fetched", "filtered", "persisted", "errors"):
        table.add_column(col)
    for r in results:
        table.add_row(r.source, str(r.fetched), str(r.filtered), str(r.persisted), str(r.errors))
    rprint(table)

    total = sum(r.persisted for r in results)
    rprint(f"[green]Inserted {total} new job(s).[/green]")


@scrape_app.command("worker")
def scrape_worker(
    loglevel: str = typer.Option("info", "--loglevel", "-l"),
    concurrency: int = typer.Option(4, "--concurrency", "-c"),
) -> None:
    """Run a Celery worker for the scrape queue."""

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "src.tasks.app",
        "worker",
        f"--loglevel={loglevel}",
        f"--concurrency={concurrency}",
        "-Q",
        "scrape",
    ]
    raise typer.Exit(code=subprocess.call(cmd))


@scrape_app.command("beat")
def scrape_beat(
    loglevel: str = typer.Option("info", "--loglevel", "-l"),
) -> None:
    """Run the Celery Beat scheduler."""

    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "src.tasks.app",
        "beat",
        f"--loglevel={loglevel}",
    ]
    raise typer.Exit(code=subprocess.call(cmd))


@scrape_app.command("dispatch")
def scrape_dispatch(
    kind: str = typer.Argument("all", help='Which dispatcher: "api", "browser", or "all".'),
) -> None:
    """Immediately enqueue dispatcher task(s) (requires running worker)."""

    from src.tasks.scrape import dispatch_api_scrapes, dispatch_browser_scrapes

    if kind in {"api", "all"}:
        res = dispatch_api_scrapes.delay()
        rprint(f"[green]Enqueued dispatch_api_scrapes id={res.id}[/green]")
    if kind in {"browser", "all"}:
        res = dispatch_browser_scrapes.delay()
        rprint(f"[green]Enqueued dispatch_browser_scrapes id={res.id}[/green]")
    if kind not in {"api", "browser", "all"}:
        rprint("[red]kind must be one of: api, browser, all[/red]")
        raise typer.Exit(code=1)


def _print_sources_summary(cfg: SourcesConfig, target: Path) -> None:
    rprint(f"[green]OK[/green] — loaded sources config from [bold]{target}[/bold]\n")
    rprint(f"defaults.locations: {cfg.defaults.locations or '(none)'}")

    table = Table(title="Companies")
    for col in ("name", "ats", "board_id/url", "priority", "enabled", "locations"):
        table.add_column(col)
    for c in cfg.companies:
        ident = c.board_id or (str(c.careers_url) if c.careers_url else "—")
        table.add_row(
            c.name,
            c.ats.value,
            ident,
            str(c.priority),
            "yes" if c.enabled else "no",
            ", ".join(c.locations) or "(defaults)",
        )
    rprint(table)

    rprint(f"LinkedIn: enabled={cfg.linkedin.enabled}, searches={len(cfg.linkedin.searches)}")
    rprint(
        f"Handshake: enabled={cfg.handshake.enabled}, school={cfg.handshake.school_subdomain}, "
        f"searches={len(cfg.handshake.searches)}"
    )


__all__ = ["scrape_app"]
