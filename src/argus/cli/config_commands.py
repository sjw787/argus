from __future__ import annotations
from pathlib import Path
from typing import Annotated, Optional
import yaml
import typer
from rich.console import Console
from rich.syntax import Syntax

from argus.core.config import load_config, reset_config_cache

config_app = typer.Typer(no_args_is_help=True)
console = Console()


@config_app.command("show")
def config_show(
    config: Annotated[Optional[Path], typer.Option("--config", "-c")] = None,
):
    """Display the active configuration."""
    reset_config_cache()
    cfg = load_config(config)
    yaml_str = yaml.dump(cfg.model_dump(), default_flow_style=False)
    console.print(Syntax(yaml_str, "yaml", theme="monokai"))


@config_app.command("validate")
def config_validate(
    config: Annotated[Optional[Path], typer.Option("--config", "-c")] = None,
):
    """Validate the configuration file."""
    reset_config_cache()
    try:
        cfg = load_config(config)
        console.print("[green]✓ Configuration is valid[/green]")
        console.print(f"  Region: {cfg.aws.region}")
        console.print(f"  Profile: {cfg.aws.profile or '(default credential chain)'}")
    except Exception as e:
        console.print(f"[red]✗ Configuration invalid:[/red] {e}")
        raise typer.Exit(1)


@config_app.command("init")
def config_init(
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("argus.yaml"),
):
    """Generate an example configuration file."""
    if output.exists():
        typer.confirm(f"'{output}' already exists. Overwrite?", abort=True)

    example = {
        "aws": {
            "region": "us-east-1",
            "profile": None,
        },
        "workgroups": {
            "output_locations": {
                "analytics_123456_prod": "s3://my-athena-results/123456/prod/",
                "analytics_123456_dev": "s3://my-athena-results/123456/dev/",
            }
        },
        "defaults": {
            "output_location": "s3://my-athena-results/default/",
            "max_results": 100,
            "query_timeout_seconds": 300,
        },
    }

    with open(output, "w") as f:
        yaml.dump(example, f, default_flow_style=False)

    console.print(f"[green]Config written to:[/green] {output}")
