from __future__ import annotations
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from rich.table import Table

from argus.core.config import load_config, reset_config_cache
from argus.core.auth import get_athena_client
from argus.core.naming import get_resolver
from argus.services.workgroup_service import WorkgroupService

workgroup_app = typer.Typer(no_args_is_help=True)
console = Console()
_state: dict = {}


@workgroup_app.callback()
def wg_callback(
    config: Annotated[Optional[Path], typer.Option("--config", "-c")] = None,
    profile: Annotated[Optional[str], typer.Option("--profile", "-p")] = None,
    region: Annotated[Optional[str], typer.Option("--region", "-r")] = None,
):
    reset_config_cache()
    cfg = load_config(config)
    _state["service"] = WorkgroupService(
        get_athena_client(profile or cfg.aws.profile, region or cfg.aws.region), cfg
    )
    _state["config"] = cfg


def _svc() -> WorkgroupService:
    return _state["service"]


@workgroup_app.command("list")
def wg_list(
    max_results: Annotated[int, typer.Option("--max", "-m")] = 50,
):
    """List all workgroups."""
    try:
        resp = _svc().list_work_groups(max_results=max_results)
        wgs = resp.get("WorkGroups", [])
        table = Table(title="Workgroups")
        table.add_column("Name", style="cyan")
        table.add_column("State")
        table.add_column("Description")
        table.add_column("Created")
        for wg in wgs:
            table.add_row(
                wg["Name"],
                wg.get("State", "-"),
                wg.get("Description", "-"),
                str(wg.get("CreationTime", "-"))[:19],
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@workgroup_app.command("get")
def wg_get(name: Annotated[str, typer.Argument()]):
    """Get workgroup details."""
    try:
        resp = _svc().get_work_group(name)
        wg = resp["WorkGroup"]
        cfg = wg.get("Configuration", {})
        rc = cfg.get("ResultConfiguration", {})

        table = Table(title=f"Workgroup: {name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        table.add_row("Name", wg["Name"])
        table.add_row("State", wg.get("State", "-"))
        table.add_row("Description", wg.get("Description", "-"))
        table.add_row("Output Location", rc.get("OutputLocation", "-"))
        table.add_row("Bytes Scanned Limit", str(cfg.get("BytesScannedCutoffPerQuery", "-")))
        table.add_row("Engine Version", str(cfg.get("EngineVersion", {}).get("SelectedEngineVersion", "-")))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@workgroup_app.command("create")
def wg_create(
    name: Annotated[str, typer.Argument()],
    description: Annotated[Optional[str], typer.Option("--description")] = None,
    output_location: Annotated[Optional[str], typer.Option("--output", "-o")] = None,
    engine_version: Annotated[Optional[str], typer.Option("--engine")] = None,
):
    """Create a new workgroup."""
    config = {}
    if output_location:
        config["ResultConfiguration"] = {"OutputLocation": output_location}
    if engine_version:
        config["EngineVersion"] = {"SelectedEngineVersion": engine_version}
    try:
        _svc().create_work_group(name, description, configuration=config or None)
        console.print(f"[green]Created workgroup:[/green] {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@workgroup_app.command("update")
def wg_update(
    name: Annotated[str, typer.Argument()],
    description: Annotated[Optional[str], typer.Option("--description")] = None,
    output_location: Annotated[Optional[str], typer.Option("--output", "-o")] = None,
    state: Annotated[Optional[str], typer.Option("--state", help="ENABLED or DISABLED")] = None,
):
    """Update a workgroup."""
    config_updates = {}
    if output_location:
        config_updates["ResultConfigurationUpdates"] = {"OutputLocation": output_location}
    try:
        _svc().update_work_group(
            name,
            description=description,
            configuration_updates=config_updates or None,
            state=state,
        )
        console.print(f"[green]Updated workgroup:[/green] {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@workgroup_app.command("delete")
def wg_delete(
    name: Annotated[str, typer.Argument()],
    recursive: Annotated[bool, typer.Option("--recursive", "-r")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
):
    """Delete a workgroup."""
    if not yes:
        typer.confirm(f"Delete workgroup '{name}'?", abort=True)
    try:
        _svc().delete_work_group(name, recursive_delete_option=recursive)
        console.print(f"[yellow]Deleted workgroup:[/yellow] {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@workgroup_app.command("resolve")
def wg_resolve(
    database: Annotated[str, typer.Argument(help="Database name to resolve workgroup for")],
    schema: Annotated[Optional[str], typer.Option("--schema", "-s")] = None,
):
    """Show which workgroup would be used for a given database name."""
    cfg = _state["config"]
    resolver = get_resolver(cfg, schema)
    if resolver is None:
        console.print("[yellow]No naming schema configured.[/yellow]")
        raise typer.Exit(1)
    wg = resolver.resolve_workgroup(database)
    parts = resolver.parse_database_name(database)
    if wg is None:
        console.print(f"[red]Database name '{database}' does not match the active naming schema.[/red]")
        raise typer.Exit(1)
    console.print(f"[cyan]Database:[/cyan] {database}")
    console.print(f"[cyan]Parsed parts:[/cyan] {parts}")
    console.print(f"[green]Resolved workgroup:[/green] {wg}")
    s3 = cfg.workgroups.output_locations.get(wg) or cfg.defaults.output_location
    console.print(f"[cyan]S3 output:[/cyan] {s3 or '(workgroup default)'}")


tags_app = typer.Typer(no_args_is_help=True)
workgroup_app.add_typer(tags_app, name="tags", help="Workgroup tag management")


@tags_app.command("list")
def tags_list(resource_arn: Annotated[str, typer.Argument(help="Resource ARN")]):
    """List tags for a resource."""
    try:
        resp = _svc().list_tags_for_resource(resource_arn)
        tags = resp.get("Tags", [])
        table = Table(title="Tags")
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        for tag in tags:
            table.add_row(tag["Key"], tag["Value"])
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@tags_app.command("add")
def tags_add(
    resource_arn: Annotated[str, typer.Argument()],
    tags: Annotated[list[str], typer.Argument(help="Tags as KEY=VALUE pairs")],
):
    """Add tags to a resource (KEY=VALUE ...)."""
    tag_dict = {}
    for t in tags:
        k, _, v = t.partition("=")
        tag_dict[k] = v
    try:
        _svc().tag_resource(resource_arn, tag_dict)
        console.print(f"[green]Tagged resource:[/green] {resource_arn}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@tags_app.command("remove")
def tags_remove(
    resource_arn: Annotated[str, typer.Argument()],
    keys: Annotated[list[str], typer.Argument(help="Tag keys to remove")],
):
    """Remove tags from a resource."""
    try:
        _svc().untag_resource(resource_arn, keys)
        console.print(f"[yellow]Removed tags from:[/yellow] {resource_arn}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
