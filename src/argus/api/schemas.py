from __future__ import annotations
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


# ── Query Models ─────────────────────────────────────────────────────────────

class ExecuteQueryRequest(BaseModel):
    sql: str
    database: str
    workgroup: Optional[str] = None
    output_location: Optional[str] = None
    schema_name: Optional[str] = None
    auto_limit: Optional[int] = 500
    result_reuse_enabled: bool = False
    result_reuse_max_age_minutes: int = Field(default=60, ge=1, le=10080)


class ExecuteQueryResponse(BaseModel):
    query_execution_id: str
    limit_applied: bool = False


class ExplainPlanType(str, Enum):
    LOGICAL = "LOGICAL"
    DISTRIBUTED = "DISTRIBUTED"
    IO = "IO"
    ANALYZE = "ANALYZE"


class ExplainQueryRequest(BaseModel):
    sql: str
    database: str
    workgroup: Optional[str] = None
    output_location: Optional[str] = None
    schema_name: Optional[str] = None
    plan_type: ExplainPlanType = ExplainPlanType.LOGICAL


class QueryStatus(BaseModel):
    state: str
    state_change_reason: Optional[str] = None
    submission_datetime: Optional[str] = None
    completion_datetime: Optional[str] = None


class QueryStats(BaseModel):
    data_scanned_bytes: Optional[int] = None
    total_execution_time_ms: Optional[int] = None
    query_queue_time_ms: Optional[int] = None
    service_processing_time_ms: Optional[int] = None


class QueryExecutionDetail(BaseModel):
    query_execution_id: str
    query: str
    database: Optional[str] = None
    workgroup: Optional[str] = None
    status: QueryStatus
    stats: QueryStats
    output_location: Optional[str] = None
    reused_previous_result: bool = False


class ResultColumn(BaseModel):
    name: str
    type: Optional[str] = None


class QueryResults(BaseModel):
    columns: list[ResultColumn]
    rows: list[list[Optional[str]]]
    next_token: Optional[str] = None
    row_count: int


class QueryListItem(BaseModel):
    query_execution_id: str
    database: Optional[str] = None
    workgroup: Optional[str] = None
    state: str
    submitted: Optional[str] = None


class NamedQueryCreate(BaseModel):
    name: str
    sql: str
    database: str
    description: Optional[str] = None
    workgroup: Optional[str] = None


class NamedQueryItem(BaseModel):
    named_query_id: str
    name: str
    database: str
    description: Optional[str] = None
    workgroup: Optional[str] = None
    query: Optional[str] = None


class PreparedStatementCreate(BaseModel):
    statement_name: str
    workgroup: str
    query: str
    description: Optional[str] = None


class PreparedStatementUpdate(BaseModel):
    query: str
    description: Optional[str] = None


class PreparedStatementItem(BaseModel):
    statement_name: str
    workgroup: str
    description: Optional[str] = None
    last_modified: Optional[str] = None


# ── Catalog Models ────────────────────────────────────────────────────────────

class DatabaseItem(BaseModel):
    name: str
    description: Optional[str] = None
    location_uri: Optional[str] = None
    parameters: dict[str, str] = Field(default_factory=dict)
    workgroup: Optional[str] = None


class DatabaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    location_uri: Optional[str] = None
    parameters: dict[str, str] = Field(default_factory=dict)


class ColumnItem(BaseModel):
    name: str
    type: str
    comment: Optional[str] = None


class TableItem(BaseModel):
    name: str
    database_name: str
    table_type: Optional[str] = None
    location: Optional[str] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    created_time: Optional[str] = None
    updated_time: Optional[str] = None
    columns: list[ColumnItem] = Field(default_factory=list)
    partition_keys: list[ColumnItem] = Field(default_factory=list)
    parameters: dict[str, str] = Field(default_factory=dict)


class TableSummary(BaseModel):
    name: str
    table_type: Optional[str] = None
    location: Optional[str] = None
    created_time: Optional[str] = None


class PartitionItem(BaseModel):
    values: list[str]
    location: Optional[str] = None
    created_time: Optional[str] = None


class ErNode(BaseModel):
    id: str
    name: str
    columns: list[ColumnItem]
    partition_keys: list[ColumnItem]


class ErEdge(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str


class ErDiagramData(BaseModel):
    nodes: list[ErNode]
    edges: list[ErEdge]


# ── Workgroup Models ──────────────────────────────────────────────────────────

class WorkgroupItem(BaseModel):
    name: str
    state: Optional[str] = None
    description: Optional[str] = None
    output_location: Optional[str] = None
    engine_version: Optional[str] = None
    created_time: Optional[str] = None


class WorkgroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    output_location: Optional[str] = None
    engine_version: Optional[str] = None
    tags: dict[str, str] = Field(default_factory=dict)


class WorkgroupUpdate(BaseModel):
    description: Optional[str] = None
    output_location: Optional[str] = None
    engine_version: Optional[str] = None
    state: Optional[str] = None


class TagItem(BaseModel):
    key: str
    value: str


# ── Config Models ─────────────────────────────────────────────────────────────

class ConfigInfo(BaseModel):
    region: str
    profile: Optional[str] = None
    workgroup_output_locations: dict[str, str]
    default_output_location: Optional[str] = None
    max_results: int
    query_timeout_seconds: int
    locked_settings: list[str] = []
    allow_download: bool = True


# ── Export ────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    format: str  # csv | json | xlsx | parquet
    delimiter: str = ","  # for CSV
    pretty: bool = False  # for JSON


# ── Auth / SSO ────────────────────────────────────────────────────────────────

class SsoStartRequest(BaseModel):
    start_url: str
    region: str


class SsoStartResponse(BaseModel):
    session_id: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class SsoPollResponse(BaseModel):
    status: str          # pending | success | expired | denied
    access_token: Optional[str] = None


class SsoAccount(BaseModel):
    account_id: str
    account_name: str
    email: str


class SsoRole(BaseModel):
    account_id: str
    role_name: str


class SsoSelectRoleRequest(BaseModel):
    session_id: str
    account_id: str
    role_name: str
    profile_name: str = "argus"


class SsoSelectRoleResponse(BaseModel):
    profile_name: str
    expiration: str
    message: str
    credential_id: Optional[str] = None  # Set in Lambda mode; send as X-Credential-Id header


class AuthStatusResponse(BaseModel):
    authenticated: bool
    profile: Optional[str] = None
    region: Optional[str] = None
    profiles: list[str] = Field(default_factory=list)


class ProfileSelectRequest(BaseModel):
    profile_name: str


class QueryStatusSnapshot(BaseModel):
    execution_id: str
    state: str
    state_change_reason: Optional[str] = None
    query: Optional[str] = None
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None


class AuthConfigResponse(BaseModel):
    mode: str  # "sso" | "cognito" | "none"
    streaming: bool = True
    cognito_user_pool_id: Optional[str] = None
    cognito_client_id: Optional[str] = None
    cognito_domain: Optional[str] = None
