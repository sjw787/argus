from __future__ import annotations
from pathlib import Path
from typing import Annotated, Optional
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from athena_beaver.core.config import load_config, reset_config_cache
from athena_beaver.core.auth import get_athena_client
from athena_beaver.services.athena_service import AthenaService

query_app = typer.Typer(no_args_is_help=True)
console = Console()

_state: dict = {}


@query_app.callback()
def query_callback(
    config: Annotated[Optional[Path], typer.Option("--config", "-c", help="Path to config file")] = None,
    profile: Annotated[Optional[str], typer.Option("--profile", "-p", help="AWS profile name")] = None,
    region: Annotated[Optional[str], typer.Option("--region", "-r", help="AWS region")] = None,
    schema: Annotated[Optional[str], typer.Option("--schema", "-s", help="Naming schema to use")] = None,
):
    reset_config_cache()
    cfg = load_config(config)
    effective_profile = profile or cfg.aws.profile
    effective_region = region or cfg.aws.region
    _state["service"] = AthenaService(
        get_athena_client(effective_profile, effective_region), cfg
    )
    _state["schema"] = schema


def _get_service() -> AthenaService:
    return _state["service"]


@query_app.command("run")
def query_run(
    sql: Annotated[str, typer.Argument(help="SQL query to execute")],
    database: Annotated[str, typer.Option("--database", "-d", help="Target database name")],
    workgroup: Annotated[Optional[str], typer.Option("--workgroup", "-w", help="Override workgroup")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Override S3 output location")] = None,
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help="Wait for query to complete")] = True,
    show_results: Annotated[bool, typer.Option("--results/--no-results", help="Show results after completion")] = True,
):
    """Run a SQL query against an Athena database (auto-resolves workgroup)."""
    svc = _get_service()
    try:
        resp = svc.start_query_execution(
            query=sql,
            database=database,
            workgroup=workgroup,
            output_location=output,
            schema_name=_state.get("schema"),
        )
        qid = resp["QueryExecutionId"]
        console.print(f"[green]Query started:[/green] {qid}")

        if wait:
            with console.status("[yellow]Waiting for query...[/yellow]"):
                final = svc.wait_for_query(qid)
            state = final["QueryExecution"]["Status"]["State"]
            reason = final["QueryExecution"]["Status"].get("StateChangeReason", "")
            if state == "SUCCEEDED":
                console.print(f"[green]✓ Query succeeded[/green]")
                if show_results:
                    _print_results(svc, qid)
            else:
                console.print(f"[red]✗ Query {state}[/red]: {reason}", style="red")
                raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@query_app.command("status")
def query_status(
    query_id: Annotated[str, typer.Argument(help="Query execution ID")],
):
    """Get the status of a query execution."""
    svc = _get_service()
    try:
        resp = svc.get_query_execution(query_id)
        qe = resp["QueryExecution"]
        status = qe["Status"]
        stats = qe.get("Statistics", {})

        table = Table(title=f"Query {query_id}")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        table.add_row("State", status["State"])
        table.add_row("Reason", status.get("StateChangeReason", "-"))
        table.add_row("Database", qe.get("QueryExecutionContext", {}).get("Database", "-"))
        table.add_row("Workgroup", qe.get("WorkGroup", "-"))
        table.add_row("Scanned (bytes)", str(stats.get("DataScannedInBytes", "-")))
        table.add_row("Exec time (ms)", str(stats.get("TotalExecutionTimeInMillis", "-")))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@query_app.command("results")
def query_results(
    query_id: Annotated[str, typer.Argument(help="Query execution ID")],
    max_results: Annotated[int, typer.Option("--max", "-m")] = 100,
):
    """Fetch and display results for a completed query."""
    svc = _get_service()
    try:
        _print_results(svc, query_id, max_results=max_results)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@query_app.command("cancel")
def query_cancel(
    query_id: Annotated[str, typer.Argument(help="Query execution ID")],
):
    """Cancel a running query."""
    svc = _get_service()
    try:
        svc.stop_query_execution(query_id)
        console.print(f"[yellow]Query {query_id} cancelled[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@query_app.command("list")
def query_list(
    workgroup: Annotated[Optional[str], typer.Option("--workgroup", "-w")] = None,
    max_results: Annotated[int, typer.Option("--max", "-m")] = 20,
):
    """List recent query executions."""
    svc = _get_service()
    try:
        resp = svc.list_query_executions(workgroup=workgroup, max_results=max_results)
        ids = resp.get("QueryExecutionIds", [])
        if not ids:
            console.print("No queries found.")
            return
        details = svc.batch_get_query_execution(ids)
        table = Table(title="Query Executions")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("State")
        table.add_column("Database")
        table.add_column("Workgroup")
        table.add_column("Submitted")
        for qe in details["QueryExecutions"]:
            status = qe["Status"]
            table.add_row(
                qe["QueryExecutionId"][:8] + "...",
                status["State"],
                qe.get("QueryExecutionContext", {}).get("Database", "-"),
                qe.get("WorkGroup", "-"),
                str(status.get("SubmissionDateTime", "-"))[:19],
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


named_app = typer.Typer(no_args_is_help=True)
query_app.add_typer(named_app, name="named", help="Named query management")


@named_app.command("create")
def named_create(
    name: Annotated[str, typer.Argument()],
    sql: Annotated[str, typer.Option("--sql", prompt=True)],
    database: Annotated[str, typer.Option("--database", "-d")],
    description: Annotated[Optional[str], typer.Option("--description")] = None,
    workgroup: Annotated[Optional[str], typer.Option("--workgroup", "-w")] = None,
):
    """Create a named query."""
    svc = _get_service()
    try:
        resp = svc.create_named_query(name, sql, database, description, workgroup)
        console.print(f"[green]Created named query:[/green] {resp['NamedQueryId']}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@named_app.command("list")
def named_list(
    workgroup: Annotated[Optional[str], typer.Option("--workgroup", "-w")] = None,
):
    """List named queries."""
    svc = _get_service()
    try:
        resp = svc.list_named_queries(workgroup=workgroup)
        ids = resp.get("NamedQueryIds", [])
        if not ids:
            console.print("No named queries found.")
            return
        details = svc.batch_get_named_query(ids)
        table = Table(title="Named Queries")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Database")
        table.add_column("Description")
        for nq in details.get("NamedQueries", []):
            table.add_row(
                nq["NamedQueryId"][:8] + "...",
                nq["Name"],
                nq.get("Database", "-"),
                nq.get("Description", "-"),
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@named_app.command("get")
def named_get(query_id: Annotated[str, typer.Argument()]):
    """Get a named query by ID."""
    svc = _get_service()
    try:
        resp = svc.get_named_query(query_id)
        nq = resp["NamedQuery"]
        table = Table(title=f"Named Query: {nq['Name']}")
        table.add_column("Field", style="cyan")
        table.add_column("Value")
        for k, v in nq.items():
            table.add_row(k, str(v))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@named_app.command("delete")
def named_delete(query_id: Annotated[str, typer.Argument()]):
    """Delete a named query."""
    svc = _get_service()
    try:
        svc.delete_named_query(query_id)
        console.print(f"[yellow]Deleted named query {query_id}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


prepared_app = typer.Typer(no_args_is_help=True)
query_app.add_typer(prepared_app, name="prepared", help="Prepared statement management")


@prepared_app.command("create")
def prepared_create(
    name: Annotated[str, typer.Argument()],
    workgroup: Annotated[str, typer.Option("--workgroup", "-w")],
    sql: Annotated[str, typer.Option("--sql", prompt=True)],
    description: Annotated[Optional[str], typer.Option("--description")] = None,
):
    """Create a prepared statement."""
    svc = _get_service()
    try:
        svc.create_prepared_statement(name, workgroup, sql, description)
        console.print(f"[green]Created prepared statement:[/green] {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@prepared_app.command("list")
def prepared_list(workgroup: Annotated[str, typer.Option("--workgroup", "-w")]):
    """List prepared statements in a workgroup."""
    svc = _get_service()
    try:
        resp = svc.list_prepared_statements(workgroup)
        stmts = resp.get("PreparedStatements", [])
        table = Table(title=f"Prepared Statements ({workgroup})")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Last Modified")
        for s in stmts:
            table.add_row(
                s["StatementName"],
                s.get("Description", "-"),
                str(s.get("LastModifiedTime", "-"))[:19],
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@prepared_app.command("get")
def prepared_get(
    name: Annotated[str, typer.Argument()],
    workgroup: Annotated[str, typer.Option("--workgroup", "-w")],
):
    """Get a prepared statement."""
    svc = _get_service()
    try:
        resp = svc.get_prepared_statement(name, workgroup)
        stmt = resp["PreparedStatement"]
        console.print(f"[cyan]Name:[/cyan] {stmt['StatementName']}")
        console.print(f"[cyan]Workgroup:[/cyan] {stmt['WorkGroupName']}")
        console.print(f"[cyan]Description:[/cyan] {stmt.get('Description', '-')}")
        console.print(f"[cyan]Query:[/cyan]\n{stmt['QueryStatement']}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@prepared_app.command("update")
def prepared_update(
    name: Annotated[str, typer.Argument()],
    workgroup: Annotated[str, typer.Option("--workgroup", "-w")],
    sql: Annotated[str, typer.Option("--sql", prompt=True)],
    description: Annotated[Optional[str], typer.Option("--description")] = None,
):
    """Update a prepared statement."""
    svc = _get_service()
    try:
        svc.update_prepared_statement(name, workgroup, sql, description)
        console.print(f"[green]Updated prepared statement:[/green] {name}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@prepared_app.command("delete")
def prepared_delete(
    name: Annotated[str, typer.Argument()],
    workgroup: Annotated[str, typer.Option("--workgroup", "-w")],
):
    """Delete a prepared statement."""
    svc = _get_service()
    try:
        svc.delete_prepared_statement(name, workgroup)
        console.print(f"[yellow]Deleted prepared statement {name}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _print_results(svc: AthenaService, query_id: str, max_results: int = 100):
    resp = svc.get_query_results(query_id, max_results=max_results)
    rows = resp.get("ResultSet", {}).get("Rows", [])
    if not rows:
        console.print("No results.")
        return
    headers = [col.get("VarCharValue", "") for col in rows[0].get("Data", [])]
    table = Table(title=f"Results: {query_id[:8]}...")
    for h in headers:
        table.add_column(h, style="cyan")
    for row in rows[1:]:
        values = [col.get("VarCharValue", "") for col in row.get("Data", [])]
        table.add_row(*values)
    console.print(table)
