from __future__ import annotations
import json
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from argus.api.schemas import (
    ExecuteQueryRequest, ExecuteQueryResponse, QueryExecutionDetail,
    QueryStatus, QueryStats, QueryResults, ResultColumn, QueryListItem,
    NamedQueryCreate, NamedQueryItem, PreparedStatementCreate,
    PreparedStatementUpdate, PreparedStatementItem, QueryStatusSnapshot,
)
from argus.api.dependencies import get_athena_service, get_config
from argus.api.sse import query_status_stream
from argus.services.athena_service import AthenaService
from argus.models.schemas import AppConfig

router = APIRouter(prefix="/queries", tags=["queries"])


def _parse_execution(qe: dict) -> QueryExecutionDetail:
    status = qe.get("Status", {})
    stats = qe.get("Statistics", {})
    ctx = qe.get("QueryExecutionContext", {})
    rc = qe.get("ResultConfiguration", {})
    return QueryExecutionDetail(
        query_execution_id=qe["QueryExecutionId"],
        query=qe.get("Query", ""),
        database=ctx.get("Database"),
        workgroup=qe.get("WorkGroup"),
        status=QueryStatus(
            state=status.get("State", "UNKNOWN"),
            state_change_reason=status.get("StateChangeReason"),
            submission_datetime=str(status.get("SubmissionDateTime", "")) or None,
            completion_datetime=str(status.get("CompletionDateTime", "")) or None,
        ),
        stats=QueryStats(
            data_scanned_bytes=stats.get("DataScannedInBytes"),
            total_execution_time_ms=stats.get("TotalExecutionTimeInMillis"),
            query_queue_time_ms=stats.get("QueryQueueTimeInMillis"),
            service_processing_time_ms=stats.get("ServiceProcessingTimeInMillis"),
        ),
        output_location=rc.get("OutputLocation"),
    )


def _has_top_level_limit(sql: str) -> bool:
    """Return True if the SQL has a LIMIT clause at the outermost query level.

    Skips string literals, line comments, block comments, and any LIMIT
    keywords that appear inside parentheses (i.e. subqueries / CTEs).
    """
    depth = 0
    i = 0
    n = len(sql)

    while i < n:
        c = sql[i]

        # Skip single- or double-quoted string literals
        if c in ("'", '"'):
            q = c
            i += 1
            while i < n:
                if sql[i] == '\\':
                    i += 2
                    continue
                if sql[i] == q:
                    i += 1
                    break
                i += 1
            continue

        # Skip line comments  (-- … \n)
        if c == '-' and i + 1 < n and sql[i + 1] == '-':
            while i < n and sql[i] != '\n':
                i += 1
            continue

        # Skip block comments  (/* … */)
        if c == '/' and i + 1 < n and sql[i + 1] == '*':
            i += 2
            while i < n - 1 and not (sql[i] == '*' and sql[i + 1] == '/'):
                i += 1
            i += 2
            continue

        if c == '(':
            depth += 1
            i += 1
            continue

        if c == ')':
            depth -= 1
            i += 1
            continue

        # Only inspect LIMIT tokens at depth 0 (top-level query)
        if depth == 0 and c in ('L', 'l') and sql[i:i + 5].upper() == 'LIMIT':
            before_ok = i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == '_')
            after = sql[i + 5:]
            # Word boundary immediately after "LIMIT"
            end_ok = not after or (not after[0].isalnum() and after[0] != '_')
            # Must be followed (after optional whitespace) by a digit
            digit_ok = bool(after.lstrip()) and after.lstrip()[0].isdigit()
            if before_ok and end_ok and digit_ok:
                return True

        i += 1

    return False


def _is_select(sql: str) -> bool:
    """Return True if the statement (ignoring leading comments/whitespace) is a SELECT."""
    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        if c in (' ', '\t', '\n', '\r'):
            i += 1
            continue
        if c == '-' and i + 1 < n and sql[i + 1] == '-':
            while i < n and sql[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and sql[i + 1] == '*':
            i += 2
            while i < n - 1 and not (sql[i] == '*' and sql[i + 1] == '/'):
                i += 1
            i += 2
            continue
        # First real token — check for SELECT or WITH (CTE)
        token = sql[i:i + 6].upper()
        return token.startswith('SELECT') or token.startswith('WITH')
    return False


def _apply_auto_limit(sql: str, limit: int) -> tuple[str, bool]:
    """Append LIMIT N to SELECT queries that have no top-level LIMIT clause."""
    stripped = sql.strip().rstrip(";")
    if not _is_select(stripped):
        return sql, False
    if _has_top_level_limit(stripped):
        return sql, False
    return f"{stripped}\nLIMIT {limit}", True


@router.post("/execute", response_model=ExecuteQueryResponse)
def execute_query(
    body: ExecuteQueryRequest,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
    config: Annotated[AppConfig, Depends(get_config)],
):
    # Unassigned databases fall back to the "primary" Athena workgroup
    if body.database and config.workgroups.assignments and body.database not in config.workgroups.assignments:
        body = body.model_copy(update={"workgroup": "primary"})

    sql = body.sql
    limit_applied = False
    if body.auto_limit and body.auto_limit > 0:
        sql, limit_applied = _apply_auto_limit(sql, body.auto_limit)

    try:
        resp = svc.start_query_execution(
            query=sql,
            database=body.database,
            workgroup=body.workgroup,
            output_location=body.output_location,
            schema_name=body.schema_name,
        )
        return ExecuteQueryResponse(query_execution_id=resp["QueryExecutionId"], limit_applied=limit_applied)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/named/list", response_model=list[NamedQueryItem])
def list_named_queries(
    svc: Annotated[AthenaService, Depends(get_athena_service)],
    workgroup: Optional[str] = Query(default=None),
):
    try:
        resp = svc.list_named_queries(workgroup=workgroup)
        ids = resp.get("NamedQueryIds", [])
        if not ids:
            return []
        details = svc.batch_get_named_query(ids)
        return [
            NamedQueryItem(
                named_query_id=nq["NamedQueryId"],
                name=nq["Name"],
                database=nq.get("Database", ""),
                description=nq.get("Description"),
                workgroup=nq.get("WorkGroup"),
                query=nq.get("QueryString"),
            )
            for nq in details.get("NamedQueries", [])
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/named", response_model=dict)
def create_named_query(
    body: NamedQueryCreate,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    try:
        resp = svc.create_named_query(body.name, body.sql, body.database, body.description, body.workgroup)
        return {"named_query_id": resp["NamedQueryId"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/named/{named_query_id}", response_model=NamedQueryItem)
def get_named_query(
    named_query_id: str,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    try:
        resp = svc.get_named_query(named_query_id)
        nq = resp["NamedQuery"]
        return NamedQueryItem(
            named_query_id=nq["NamedQueryId"],
            name=nq["Name"],
            database=nq.get("Database", ""),
            description=nq.get("Description"),
            workgroup=nq.get("WorkGroup"),
            query=nq.get("QueryString"),
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/named/{named_query_id}")
def delete_named_query(
    named_query_id: str,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    try:
        svc.delete_named_query(named_query_id)
        return {"message": f"Named query {named_query_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/prepared/list", response_model=list[PreparedStatementItem])
def list_prepared_statements(
    svc: Annotated[AthenaService, Depends(get_athena_service)],
    workgroup: str = Query(...),
):
    try:
        resp = svc.list_prepared_statements(workgroup)
        return [
            PreparedStatementItem(
                statement_name=s["StatementName"],
                workgroup=workgroup,
                description=s.get("Description"),
                last_modified=str(s.get("LastModifiedTime", "")) or None,
            )
            for s in resp.get("PreparedStatements", [])
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/prepared")
def create_prepared_statement(
    body: PreparedStatementCreate,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    try:
        svc.create_prepared_statement(body.statement_name, body.workgroup, body.query, body.description)
        return {"message": f"Prepared statement {body.statement_name} created"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/prepared/{statement_name}")
def update_prepared_statement(
    statement_name: str,
    body: PreparedStatementUpdate,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
    workgroup: str = Query(...),
):
    try:
        svc.update_prepared_statement(statement_name, workgroup, body.query, body.description)
        return {"message": f"Prepared statement {statement_name} updated"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/prepared/{statement_name}")
def delete_prepared_statement(
    statement_name: str,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
    workgroup: str = Query(...),
):
    try:
        svc.delete_prepared_statement(statement_name, workgroup)
        return {"message": f"Prepared statement {statement_name} deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[QueryListItem])
def list_queries(
    svc: Annotated[AthenaService, Depends(get_athena_service)],
    config: Annotated[AppConfig, Depends(get_config)],
    workgroup: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=50),
    next_token: Optional[str] = Query(default=None),
):
    try:
        all_ids: list[str] = []

        if workgroup:
            workgroups_to_query = [workgroup]
        else:
            # Collect all configured workgroups; fall back to 'primary'
            configured = set(config.workgroups.output_locations.keys()) if config.workgroups.output_locations else set()
            configured.add("primary")
            workgroups_to_query = list(configured)

        for wg in workgroups_to_query:
            try:
                resp = svc.list_query_executions(workgroup=wg, max_results=limit, next_token=next_token)
                all_ids.extend(resp.get("QueryExecutionIds", []))
            except Exception:
                pass  # skip workgroups we can't access

        if not all_ids:
            return []

        # De-duplicate and cap results
        seen: set[str] = set()
        unique_ids = [i for i in all_ids if not (i in seen or seen.add(i))]  # type: ignore[func-returns-value]
        unique_ids = unique_ids[:limit]

        details = svc.batch_get_query_execution(unique_ids)
        result = []
        for qe in details.get("QueryExecutions", []):
            status = qe.get("Status", {})
            ctx = qe.get("QueryExecutionContext", {})
            result.append(QueryListItem(
                query_execution_id=qe["QueryExecutionId"],
                database=ctx.get("Database"),
                workgroup=qe.get("WorkGroup"),
                state=status.get("State", "UNKNOWN"),
                submitted=str(status.get("SubmissionDateTime", "")) or None,
            ))
        # Sort newest first
        result.sort(key=lambda q: q.submitted or "", reverse=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{query_id}", response_model=QueryExecutionDetail)
def get_query(
    query_id: str,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    try:
        resp = svc.get_query_execution(query_id)
        return _parse_execution(resp["QueryExecution"])
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{query_id}/status", response_model=QueryStatusSnapshot)
def get_query_status(
    query_id: str,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    """Single-shot status check — compatible with API Gateway (no streaming)."""
    try:
        resp = svc.get_query_execution(query_id)
        qe = resp["QueryExecution"]
        status = qe.get("Status", {})
        return QueryStatusSnapshot(
            execution_id=query_id,
            state=status.get("State", "UNKNOWN"),
            state_change_reason=status.get("StateChangeReason"),
            query=qe.get("Query"),
            submitted_at=str(status.get("SubmissionDateTime", "")) or None,
            completed_at=str(status.get("CompletionDateTime", "")) or None,
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{query_id}/stream")
def stream_query_status(
    query_id: str,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    async def generator():
        async for event in query_status_stream(query_id, svc):
            yield {"data": json.dumps(event)}
    return EventSourceResponse(generator())


@router.get("/{query_id}/results", response_model=QueryResults)
def get_query_results(
    query_id: str,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
    page_size: int = Query(default=100, le=1000),
    next_token: Optional[str] = Query(default=None),
):
    try:
        resp = svc.get_query_results(query_id, max_results=page_size, next_token=next_token)
        result_set = resp.get("ResultSet", {})
        rows_raw = result_set.get("Rows", [])
        meta = result_set.get("ResultSetMetadata", {})
        col_info = meta.get("ColumnInfo", [])

        if not rows_raw:
            return QueryResults(columns=[], rows=[], next_token=resp.get("NextToken"), row_count=0)

        if col_info:
            columns = [ResultColumn(name=c["Name"], type=c.get("Type")) for c in col_info]
            data_rows = rows_raw[1:]  # Athena always includes header row first, skip it
        else:
            header_row = rows_raw[0]
            columns = [ResultColumn(name=d.get("VarCharValue", ""), type=None) for d in header_row.get("Data", [])]
            data_rows = rows_raw[1:]

        rows = [
            [cell.get("VarCharValue") for cell in row.get("Data", [])]
            for row in data_rows
        ]
        return QueryResults(
            columns=columns,
            rows=rows,
            next_token=resp.get("NextToken"),
            row_count=len(rows),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{query_id}/cancel")
def cancel_query(
    query_id: str,
    svc: Annotated[AthenaService, Depends(get_athena_service)],
):
    try:
        svc.stop_query_execution(query_id)
        return {"message": f"Query {query_id} cancelled"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
