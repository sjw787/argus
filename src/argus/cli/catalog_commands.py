from __future__ import annotations
from pathlib import Path
from typing import Annotated, Optional
import json
import typer
from rich.console import Console
from rich.table import Table

from argus.core.config import load_config, reset_config_cache
from argus.core.auth import get_glue_client
from argus.services.catalog_service import CatalogService

catalog_app = typer.Typer(no_args_is_help=True)
console = Console()

_state: dict = {}


@catalog_app.callback()
def catalog_callback(
    config: Annotated[Optional[Path], typer.Option("--config", "-c")] = None,
    profile: Annotated[Optional[str], typer.Option("--profile", "-p")] = None,
    region: Annotated[Optional[str], typer.Option("--region", "-r")] = None,
    schema: Annotated[Optional[str], typer.Option("--schema", "-s")] = None,
):
    reset_config_cache()
    cfg = load_config(config)
    _state["service"] = CatalogService(
        get_glue_client(profile or cfg.aws.profile, region or cfg.aws.region), cfg
    )
    _state["schema"] = schema


def _svc() -> CatalogService:
    return _state["service"]


db_app = typer.Typer(no_args_is_help=True)
catalog_app.add_typer(db_app, name="databases", help="Database management")


@db_app.command("list")
def db_list(
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
    max_results: Annotated[int, typer.Option("--max", "-m")] = 100,
):
    """List all databases in the catalog."""
    try:
        resp = _svc().list_databases(catalog_id=catalog_id, max_results=max_results)
        dbs = resp.get("DatabaseList", [])
        table = Table(title="Databases")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Location")
        for db in dbs:
            table.add_row(db["Name"], db.get("Description", "-"), db.get("LocationUri", "-"))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@db_app.command("get")
def db_get(
    name: Annotated[str, typer.Argument()],
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
):
    """Get details of a specific database."""
    try:
        resp = _svc().get_database(name, catalog_id)
        db = resp["Database"]
        table = Table(title=f"Database: {name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        table.add_row("Name", db["Name"])
        table.add_row("Description", db.get("Description", "-"))
        table.add_row("Location", db.get("LocationUri", "-"))
        table.add_row("Parameters", json.dumps(db.get("Parameters", {})))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@db_app.command("create")
def db_create(
    name: Annotated[str, typer.Argument()],
    description: Annotated[Optional[str], typer.Option("--description")] = None,
    location: Annotated[Optional[str], typer.Option("--location")] = None,
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
):
    """Create a new database."""
    try:
        _svc().create_database(name, description, location, catalog_id=catalog_id)
        console.print(f"[green]Created database:[/green] {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@db_app.command("delete")
def db_delete(
    name: Annotated[str, typer.Argument()],
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
):
    """Delete a database."""
    if not yes:
        typer.confirm(f"Delete database '{name}'?", abort=True)
    try:
        _svc().delete_database(name, catalog_id)
        console.print(f"[yellow]Deleted database:[/yellow] {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@catalog_app.command("search")
def catalog_search(
    client_id: Annotated[str, typer.Option("--client-id", "-c", help="Client ID to search for")],
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
):
    """Find all databases belonging to a specific client."""
    try:
        dbs = _svc().search_databases_by_client_id(
            client_id, schema_name=_state.get("schema"), catalog_id=catalog_id
        )
        if not dbs:
            console.print(f"No databases found for client '{client_id}'")
            return
        table = Table(title=f"Databases for Client: {client_id}")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        for db in dbs:
            table.add_row(db["Name"], db.get("Description", "-"))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


tables_app = typer.Typer(no_args_is_help=True)
catalog_app.add_typer(tables_app, name="tables", help="Table management")


@tables_app.command("list")
def tables_list(
    database: Annotated[str, typer.Option("--database", "-d")],
    expression: Annotated[Optional[str], typer.Option("--filter", "-f")] = None,
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
):
    """List tables in a database."""
    try:
        resp = _svc().list_tables(database, catalog_id=catalog_id, expression=expression)
        tables_list_data = resp.get("TableList", [])
        table = Table(title=f"Tables in {database}")
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Location")
        table.add_column("Created")
        for t in tables_list_data:
            sd = t.get("StorageDescriptor", {})
            table.add_row(
                t["Name"],
                t.get("TableType", "-"),
                sd.get("Location", "-"),
                str(t.get("CreateTime", "-"))[:19],
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@tables_app.command("get")
def tables_get(
    name: Annotated[str, typer.Argument()],
    database: Annotated[str, typer.Option("--database", "-d")],
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
):
    """Get table details including schema."""
    try:
        resp = _svc().get_table(database, name, catalog_id)
        t = resp["Table"]
        sd = t.get("StorageDescriptor", {})

        console.print(f"\n[bold cyan]Table:[/bold cyan] {t['Name']}")
        console.print(f"[cyan]Database:[/cyan] {database}")
        console.print(f"[cyan]Type:[/cyan] {t.get('TableType', '-')}")
        console.print(f"[cyan]Location:[/cyan] {sd.get('Location', '-')}")
        console.print(f"[cyan]Format:[/cyan] {sd.get('InputFormat', '-')}")

        cols = sd.get("Columns", [])
        if cols:
            col_table = Table(title="Columns")
            col_table.add_column("Name", style="cyan")
            col_table.add_column("Type")
            col_table.add_column("Comment")
            for col in cols:
                col_table.add_row(col["Name"], col["Type"], col.get("Comment", ""))
            console.print(col_table)

        part_keys = t.get("PartitionKeys", [])
        if part_keys:
            pk_table = Table(title="Partition Keys")
            pk_table.add_column("Name", style="cyan")
            pk_table.add_column("Type")
            for pk in part_keys:
                pk_table.add_row(pk["Name"], pk["Type"])
            console.print(pk_table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@tables_app.command("delete")
def tables_delete(
    name: Annotated[str, typer.Argument()],
    database: Annotated[str, typer.Option("--database", "-d")],
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
):
    """Delete a table."""
    if not yes:
        typer.confirm(f"Delete table '{name}' from '{database}'?", abort=True)
    try:
        _svc().delete_table(database, name, catalog_id)
        console.print(f"[yellow]Deleted table:[/yellow] {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


partitions_app = typer.Typer(no_args_is_help=True)
catalog_app.add_typer(partitions_app, name="partitions", help="Partition management")


@partitions_app.command("list")
def partitions_list(
    database: Annotated[str, typer.Option("--database", "-d")],
    table: Annotated[str, typer.Option("--table", "-t")],
    expression: Annotated[Optional[str], typer.Option("--filter", "-f")] = None,
    catalog_id: Annotated[Optional[str], typer.Option("--catalog")] = None,
    max_results: Annotated[int, typer.Option("--max", "-m")] = 100,
):
    """List partitions for a table."""
    try:
        resp = _svc().get_partitions(
            database, table, catalog_id=catalog_id, expression=expression, max_results=max_results
        )
        parts = resp.get("Partitions", [])
        p_table = Table(title=f"Partitions: {database}.{table}")
        p_table.add_column("Values", style="cyan")
        p_table.add_column("Location")
        p_table.add_column("Created")
        for p in parts:
            sd = p.get("StorageDescriptor", {})
            p_table.add_row(
                str(p.get("Values", [])),
                sd.get("Location", "-"),
                str(p.get("CreationTime", "-"))[:19],
            )
        console.print(p_table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
