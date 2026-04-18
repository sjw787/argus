from __future__ import annotations
import re
import time
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from argus.api.schemas import (
    DatabaseItem, DatabaseCreate, TableItem, TableSummary,
    ColumnItem, PartitionItem, ErDiagramData, ErNode, ErEdge,
)
from argus.api.dependencies import get_catalog_service, get_config, get_athena_service
from argus.services.catalog_service import CatalogService
from argus.services.athena_service import AthenaService
from argus.models.schemas import AppConfig
from argus.api.errors import sanitize_error

router = APIRouter(prefix="/catalog", tags=["catalog"])


# ── Database list cache ───────────────────────────────────────────────────────

class _DbCache:
    TTL = 60  # seconds

    def __init__(self) -> None:
        self._data: dict[tuple, tuple[list[DatabaseItem], float]] = {}

    def get(self, key: tuple) -> list[DatabaseItem] | None:
        entry = self._data.get(key)
        if entry and time.monotonic() - entry[1] < self.TTL:
            return entry[0]
        return None

    def set(self, key: tuple, items: list[DatabaseItem]) -> None:
        self._data[key] = (items, time.monotonic())

    def invalidate(self, key: tuple) -> None:
        self._data.pop(key, None)

    def invalidate_all(self) -> None:
        self._data.clear()


_db_cache = _DbCache()


class PaginatedDatabaseResponse(BaseModel):
    items: list[DatabaseItem]
    total: int
    offset: int
    limit: int
    has_more: bool


def _parse_columns(cols: list[dict]) -> list[ColumnItem]:
    return [ColumnItem(name=c["Name"], type=c.get("Type", ""), comment=c.get("Comment")) for c in cols]


def _parse_table(t: dict, db_name: str) -> TableItem:
    sd = t.get("StorageDescriptor", {})
    return TableItem(
        name=t["Name"],
        database_name=db_name,
        table_type=t.get("TableType"),
        location=sd.get("Location"),
        input_format=sd.get("InputFormat"),
        output_format=sd.get("OutputFormat"),
        created_time=str(t.get("CreateTime", "")) or None,
        updated_time=str(t.get("UpdateTime", "")) or None,
        columns=_parse_columns(sd.get("Columns", [])),
        partition_keys=_parse_columns(t.get("PartitionKeys", [])),
        parameters=t.get("Parameters", {}),
    )


@router.get("/databases", response_model=PaginatedDatabaseResponse)
def list_databases(
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    config: Annotated[AppConfig, Depends(get_config)],
    catalog_id: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    profile: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
):
    """Paginated database listing with optional server-side search.
    All pages are fetched from Glue and cached for 60 s per (catalog, profile, region)."""
    try:
        cache_key = (catalog_id, profile or config.aws.profile, region or config.aws.region)
        all_dbs = _db_cache.get(cache_key)
        if all_dbs is None:
            assignments = config.workgroups.assignments
            all_dbs = []
            next_token = None
            while True:
                resp = svc.list_databases(catalog_id=catalog_id, next_token=next_token)
                for db in resp.get("DatabaseList", []):
                    db_name = db["Name"]
                    wg = assignments.get(db_name)
                    all_dbs.append(DatabaseItem(
                        name=db_name,
                        description=db.get("Description"),
                        location_uri=db.get("LocationUri"),
                        parameters=db.get("Parameters", {}),
                        workgroup=wg,
                    ))
                next_token = resp.get("NextToken")
                if not next_token:
                    break
            _db_cache.set(cache_key, all_dbs)

        # Server-side search filter
        filtered = all_dbs
        if search:
            q = search.lower()
            filtered = [db for db in all_dbs if q in db.name.lower()]

        page = filtered[offset: offset + limit]
        return PaginatedDatabaseResponse(
            items=page,
            total=len(filtered),
            offset=offset,
            limit=limit,
            has_more=(offset + limit) < len(filtered),
        )
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.get("/databases/{name}", response_model=DatabaseItem)
def get_database(
    name: str,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    catalog_id: Optional[str] = Query(default=None),
):
    try:
        resp = svc.get_database(name, catalog_id)
        db = resp["Database"]
        return DatabaseItem(
            name=db["Name"],
            description=db.get("Description"),
            location_uri=db.get("LocationUri"),
            parameters=db.get("Parameters", {}),
        )
    except Exception as e:
        raise sanitize_error(e, status_code=404, public_message="Catalog operation failed")


@router.post("/databases", response_model=DatabaseItem)
def create_database(
    body: DatabaseCreate,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
):
    try:
        svc.create_database(body.name, body.description, body.location_uri, body.parameters or None)
        _db_cache.invalidate_all()
        return DatabaseItem(name=body.name, description=body.description, location_uri=body.location_uri)
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.delete("/databases/{name}")
def delete_database(
    name: str,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    catalog_id: Optional[str] = Query(default=None),
):
    try:
        svc.delete_database(name, catalog_id)
        _db_cache.invalidate_all()
        return {"message": f"Database {name} deleted"}
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.get("/databases/information_schema/tables", response_model=list[TableSummary])
def list_information_schema_tables(
    athena: Annotated[AthenaService, Depends(get_athena_service)],
):
    """Query Athena directly to list tables in information_schema (not in Glue)."""
    # These tables exist in information_schema.tables but are not queryable via the Glue connector
    UNSUPPORTED = {"table_privileges", "role_table_grants", "enabled_roles", "applicable_roles", "roles"}
    try:
        sql = (
            "SELECT table_name, table_type "
            "FROM information_schema.tables "
            "WHERE table_schema = 'information_schema' "
            "ORDER BY table_name"
        )
        exec_resp = athena.start_query_execution(
            query=sql,
            database="information_schema",
            workgroup="primary",
        )
        qid = exec_resp["QueryExecutionId"]
        final = athena.wait_for_query(qid, poll_interval=0.5, timeout=30)
        state = final["QueryExecution"]["Status"]["State"]
        if state != "SUCCEEDED":
            reason = final["QueryExecution"]["Status"].get("StateChangeReason", "Query failed")
            raise HTTPException(status_code=400, detail=reason)
        results = athena.get_query_results(qid)
        rows = results.get("ResultSet", {}).get("Rows", [])
        # Skip header row; filter out unsupported tables
        tables = []
        for row in rows[1:]:
            cells = [c.get("VarCharValue", "") for c in row.get("Data", [])]
            if len(cells) >= 1 and cells[0] and cells[0] not in UNSUPPORTED:
                tables.append(TableSummary(
                    name=cells[0],
                    table_type="VIRTUAL_VIEW" if len(cells) >= 2 and cells[1] == "VIEW" else None,
                    location=None,
                    created_time=None,
                ))
        return tables
    except HTTPException:
        raise
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.get("/databases/{db_name}/tables", response_model=list[TableSummary])
def list_tables(
    db_name: str,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    catalog_id: Optional[str] = Query(default=None),
    expression: Optional[str] = Query(default=None),
    max_results: int = Query(default=100),
):
    try:
        resp = svc.list_tables(db_name, catalog_id=catalog_id, expression=expression, max_results=max_results)
        return [
            TableSummary(
                name=t["Name"],
                table_type=t.get("TableType"),
                location=t.get("StorageDescriptor", {}).get("Location"),
                created_time=str(t.get("CreateTime", "")) or None,
            )
            for t in resp.get("TableList", [])
        ]
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.get("/databases/information_schema/tables/{table_name}", response_model=TableItem)
def get_information_schema_table(
    table_name: str,
    athena: Annotated[AthenaService, Depends(get_athena_service)],
):
    """Query Athena information_schema.columns to describe a virtual table."""
    if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
        raise HTTPException(status_code=400, detail="Invalid table name")
    try:
        sql = (
            f"SELECT column_name, data_type "
            f"FROM information_schema.columns "
            f"WHERE table_schema = 'information_schema' "
            f"AND table_name = '{table_name}' "
            f"ORDER BY ordinal_position"
        )
        exec_resp = athena.start_query_execution(
            query=sql,
            database="information_schema",
            workgroup="primary",
        )
        qid = exec_resp["QueryExecutionId"]
        final = athena.wait_for_query(qid, poll_interval=0.5, timeout=30)
        state = final["QueryExecution"]["Status"]["State"]
        if state != "SUCCEEDED":
            reason = final["QueryExecution"]["Status"].get("StateChangeReason", "Query failed")
            raise HTTPException(status_code=400, detail=reason)
        results = athena.get_query_results(qid)
        rows = results.get("ResultSet", {}).get("Rows", [])
        columns = []
        for row in rows[1:]:
            cells = [c.get("VarCharValue", "") for c in row.get("Data", [])]
            if len(cells) >= 1 and cells[0]:
                columns.append(ColumnItem(name=cells[0], type=cells[1] if len(cells) > 1 else ""))
        return TableItem(
            name=table_name,
            database_name="information_schema",
            table_type="VIRTUAL_VIEW",
            columns=columns,
            partition_keys=[],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.get("/databases/{db_name}/tables/{table_name}", response_model=TableItem)
def get_table(
    db_name: str,
    table_name: str,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    catalog_id: Optional[str] = Query(default=None),
):
    try:
        resp = svc.get_table(db_name, table_name, catalog_id)
        return _parse_table(resp["Table"], db_name)
    except Exception as e:
        raise sanitize_error(e, status_code=404, public_message="Catalog operation failed")


@router.delete("/databases/{db_name}/tables/{table_name}")
def delete_table(
    db_name: str,
    table_name: str,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    catalog_id: Optional[str] = Query(default=None),
):
    try:
        svc.delete_table(db_name, table_name, catalog_id)
        return {"message": f"Table {table_name} deleted from {db_name}"}
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.get("/databases/{db_name}/tables/{table_name}/partitions", response_model=list[PartitionItem])
def list_partitions(
    db_name: str,
    table_name: str,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    catalog_id: Optional[str] = Query(default=None),
    expression: Optional[str] = Query(default=None),
    max_results: int = Query(default=100),
):
    try:
        resp = svc.get_partitions(db_name, table_name, catalog_id=catalog_id, expression=expression, max_results=max_results)
        return [
            PartitionItem(
                values=p.get("Values", []),
                location=p.get("StorageDescriptor", {}).get("Location"),
                created_time=str(p.get("CreationTime", "")) or None,
            )
            for p in resp.get("Partitions", [])
        ]
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.get("/databases/{db_name}/tables/{table_name}/versions")
def get_table_versions(
    db_name: str,
    table_name: str,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    catalog_id: Optional[str] = Query(default=None),
):
    try:
        resp = svc.get_table_versions(db_name, table_name, catalog_id=catalog_id)
        return resp.get("TableVersions", [])
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")


@router.get("/databases/{db_name}/er-diagram", response_model=ErDiagramData)
def get_er_diagram(
    db_name: str,
    svc: Annotated[CatalogService, Depends(get_catalog_service)],
    catalog_id: Optional[str] = Query(default=None),
):
    """Return ER diagram data with tables as nodes and inferred FK relationships as edges."""
    try:
        resp = svc.list_tables(db_name, catalog_id=catalog_id, max_results=200)
        tables = resp.get("TableList", [])
        table_names = {t["Name"] for t in tables}

        nodes = []
        # Map table name -> list of column names for relationship inference
        table_cols: dict[str, list[str]] = {}

        for t in tables:
            sd = t.get("StorageDescriptor", {})
            cols = _parse_columns(sd.get("Columns", []))
            pk = _parse_columns(t.get("PartitionKeys", []))
            nodes.append(ErNode(id=t["Name"], name=t["Name"], columns=cols, partition_keys=pk))
            table_cols[t["Name"]] = [c.name.lower() for c in cols + pk]

        edges = []
        seen_edges: set[tuple[str, str]] = set()

        def _add_edge(src: str, src_col: str, tgt: str, tgt_col: str) -> None:
            key = (min(src, tgt), max(src, tgt), src_col)
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append(ErEdge(source_table=src, source_column=src_col,
                                    target_table=tgt, target_column=tgt_col))

        # Build candidate target names for each table (name + stripped plurals/singulars)
        def _candidates(name: str) -> set[str]:
            opts = {name}
            if name.endswith("s"):
                opts.add(name[:-1])   # sessions → session
            else:
                opts.add(name + "s")  # session → sessions
            if name.endswith("es"):
                opts.add(name[:-2])
            return opts

        for tname, col_names in table_cols.items():
            for col_lower in col_names:
                # Pattern 1: col is exactly "{other}_id" or "{other}id"
                for other in table_names:
                    if other == tname:
                        continue
                    for cand in _candidates(other):
                        if col_lower in (f"{cand}_id", f"{cand}id"):
                            _add_edge(tname, col_lower, other, "id")

                # Pattern 2: col ends in "_id" — strip suffix, check candidates
                if col_lower.endswith("_id") and col_lower != "id":
                    prefix = col_lower[:-3]  # e.g. "session" from "session_id"
                    for other in table_names:
                        if other == tname:
                            continue
                        if other in _candidates(prefix):
                            _add_edge(tname, col_lower, other, "id")

        return ErDiagramData(nodes=nodes, edges=edges)
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Catalog operation failed")
