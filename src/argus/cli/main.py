from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console

from argus.cli.athena_commands import query_app
from argus.cli.catalog_commands import catalog_app
from argus.cli.workgroup_commands import workgroup_app
from argus.cli.config_commands import config_app

app = typer.Typer(
    name="argus",
    help="AWS Athena DBMS CLI with automatic workgroup routing",
    no_args_is_help=True,
)
console = Console()

app.add_typer(query_app, name="query", help="Athena query operations")
app.add_typer(catalog_app, name="catalog", help="Glue Data Catalog operations")
app.add_typer(workgroup_app, name="workgroup", help="Athena workgroup management")
app.add_typer(config_app, name="config", help="Configuration management")


@app.command("ui")
def launch_ui(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to"),
    port: int = typer.Option(8000, help="Port to run the server on"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Auto-open browser"),
    dev: bool = typer.Option(False, "--dev", help="Enable hot reload (dev mode)"),
):
    """Launch the Argus for Athena web UI."""
    from argus.api.app import run_server
    console.print(f"[green]Starting Argus for Athena UI at http://{host}:{port}[/green]")
    run_server(host=host, port=port, config_path=config, open_browser=open_browser, reload=dev)


if __name__ == "__main__":
    app()
