from __future__ import annotations
import json
import logging
import os
import threading
import time
import uuid
from typing import Optional

log = logging.getLogger(__name__)

# Action type constants — used in audit log records.
ACTION_QUERY_EXECUTE  = "QUERY_EXECUTE"
ACTION_QUERY_CANCEL   = "QUERY_CANCEL"
ACTION_EXPORT         = "EXPORT"
ACTION_LOGIN          = "LOGIN"
ACTION_LOGOUT         = "LOGOUT"
ACTION_CONFIG_CHANGE  = "CONFIG_CHANGE"
ACTION_CATALOG_READ   = "CATALOG_READ"
ACTION_EXPLAIN        = "EXPLAIN"
ACTION_OTHER          = "OTHER"

# Map (method, path-prefix) → action type for automatic classification.
_ACTION_MAP: list[tuple[str, str, str]] = [
    ("POST",   "/api/v1/queries/execute",  ACTION_QUERY_EXECUTE),
    ("POST",   "/api/v1/explain",          ACTION_EXPLAIN),
    ("POST",   "/api/v1/queries/",         ACTION_QUERY_CANCEL),
    ("DELETE", "/api/v1/queries/",         ACTION_QUERY_CANCEL),
    ("GET",    "/api/v1/export",           ACTION_EXPORT),
    ("POST",   "/api/v1/auth/login",       ACTION_LOGIN),
    ("POST",   "/api/v1/auth/logout",      ACTION_LOGOUT),
    ("PUT",    "/api/v1/config",           ACTION_CONFIG_CHANGE),
    ("PATCH",  "/api/v1/config",           ACTION_CONFIG_CHANGE),
    ("GET",    "/api/v1/catalog",          ACTION_CATALOG_READ),
]


def _classify_action(method: str, path: str) -> str:
    for m, prefix, action in _ACTION_MAP:
        if method.upper() == m and path.startswith(prefix):
            return action
    return ACTION_OTHER


class AuditLogger:
    """Structured audit logger that writes metadata-only records to CloudWatch.

    Completely disabled (no-op) when ARGUS_AUDIT_LOGGING is not set to a
    truthy value — zero overhead for non-government deployments.

    Fields logged per event:
        timestamp, request_id, user_identity, action_type,
        http_method, path, status_code, duration_ms,
        database (if present in query params), workgroup (if present),
        execution_id (if returned in response body)

    Fields NEVER logged:
        SQL query text, result data, column values, row data.
    """

    def __init__(self) -> None:
        self._enabled = os.environ.get("ARGUS_AUDIT_LOGGING", "").lower() in (
            "1", "true", "yes"
        )
        self._log_group = os.environ.get("ARGUS_AUDIT_LOG_GROUP", "")
        self._stream_name: Optional[str] = None
        self._sequence_token: Optional[str] = None
        self._cw_client = None
        self._lock = threading.Lock()

        if self._enabled:
            self._init_cloudwatch()

    def _init_cloudwatch(self) -> None:
        if not self._log_group:
            log.warning(
                "ARGUS_AUDIT_LOGGING=true but ARGUS_AUDIT_LOG_GROUP is not set; "
                "audit events will be written to the application log instead."
            )
            return
        try:
            import boto3
            from argus.services.aws_endpoints import get_endpoint_url
            region = os.environ.get("ARGUS_REGION", "us-east-1")
            endpoint_url = get_endpoint_url("logs", region)
            self._cw_client = boto3.client(
                "logs", region_name=region, endpoint_url=endpoint_url
            )
            self._stream_name = f"argus-{uuid.uuid4().hex[:8]}"
            self._cw_client.create_log_stream(
                logGroupName=self._log_group,
                logStreamName=self._stream_name,
            )
        except Exception as exc:  # pragma: no cover
            log.error("Failed to initialise CloudWatch audit log stream: %s", exc)
            self._cw_client = None

    # ── Public API ────────────────────────────────────────────────────────────

    def log_action(
        self,
        *,
        user_identity: str,
        action_type: str,
        http_method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: Optional[str] = None,
        database: Optional[str] = None,
        workgroup: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> None:
        """Record one audit event.  No-op when audit logging is disabled."""
        if not self._enabled:
            return

        record: dict = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": request_id or str(uuid.uuid4()),
            "user_identity": user_identity,
            "action_type": action_type,
            "http_method": http_method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }
        if database:
            record["database"] = database
        if workgroup:
            record["workgroup"] = workgroup
        if execution_id:
            record["execution_id"] = execution_id

        self._emit(record)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _emit(self, record: dict) -> None:
        message = json.dumps(record, separators=(",", ":"))
        if self._cw_client and self._stream_name:
            self._emit_to_cloudwatch(message)
        else:
            # Fallback: write to application logger (still captured by Lambda logs)
            log.info("AUDIT %s", message)

    def _emit_to_cloudwatch(self, message: str) -> None:
        try:
            with self._lock:
                kwargs: dict = {
                    "logGroupName": self._log_group,
                    "logStreamName": self._stream_name,
                    "logEvents": [
                        {"timestamp": int(time.time() * 1000), "message": message}
                    ],
                }
                if self._sequence_token:
                    kwargs["sequenceToken"] = self._sequence_token
                response = self._cw_client.put_log_events(**kwargs)
                self._sequence_token = response.get("nextSequenceToken")
        except Exception as exc:  # pragma: no cover
            log.error("Failed to write audit event to CloudWatch: %s", exc)


# Module-level singleton — created once per Lambda cold start.
audit_logger = AuditLogger()
