"""Functional tests: end-to-end query execution → poll status → fetch results."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from argus.api.app import create_app
from argus.api.dependencies import get_athena_service, get_config
from argus.models.schemas import AppConfig


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_client() -> tuple[TestClient, MagicMock]:
    app = create_app()
    mock_svc = MagicMock()
    app.dependency_overrides[get_config] = lambda: AppConfig()
    app.dependency_overrides[get_athena_service] = lambda: mock_svc
    return TestClient(app), mock_svc


def _stub_execution(mock_svc, query_id: str, state: str = "SUCCEEDED") -> None:
    mock_svc.get_query_execution.return_value = {
        "QueryExecution": {
            "QueryExecutionId": query_id,
            "Query": "SELECT 1",
            "Status": {"State": state},
            "Statistics": {},
            "QueryExecutionContext": {"Database": "mydb"},
            "ResultConfiguration": {},
        }
    }


def _stub_results(
    mock_svc,
    headers: list[str],
    rows: list[list[str]],
    next_token: str | None = None,
) -> None:
    raw_rows = [{"Data": [{"VarCharValue": h} for h in headers]}]
    for row in rows:
        raw_rows.append({"Data": [{"VarCharValue": v} for v in row]})
    mock_svc.get_query_results.return_value = {
        "ResultSet": {"Rows": raw_rows, "ResultSetMetadata": {"ColumnInfo": []}},
        **({"NextToken": next_token} if next_token else {}),
    }


# ── Execute → status → results flow ──────────────────────────────────────────

def test_execute_returns_query_execution_id():
    client, mock_svc = _make_client()
    mock_svc.start_query_execution.return_value = {"QueryExecutionId": "qid-001"}

    resp = client.post(
        "/api/v1/queries/execute",
        json={"sql": "SELECT 1", "database": "mydb"},
    )

    assert resp.status_code == 200
    assert resp.json()["query_execution_id"] == "qid-001"


def test_status_endpoint_returns_state():
    client, mock_svc = _make_client()
    _stub_execution(mock_svc, "qid-001", state="RUNNING")

    resp = client.get("/api/v1/queries/qid-001/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_id"] == "qid-001"
    assert data["state"] == "RUNNING"


def test_results_endpoint_returns_rows():
    client, mock_svc = _make_client()
    _stub_results(mock_svc, ["id", "name"], [["1", "Alice"], ["2", "Bob"]])

    resp = client.get("/api/v1/queries/qid-001/results")

    assert resp.status_code == 200
    data = resp.json()
    assert data["row_count"] == 2
    assert data["columns"][0]["name"] == "id"
    assert data["rows"][0] == ["1", "Alice"]
    assert data["rows"][1] == ["2", "Bob"]


def test_full_query_flow_execute_then_poll_then_results():
    """Simulate a realistic client flow: execute → check status → get results."""
    client, mock_svc = _make_client()

    # Step 1: submit
    mock_svc.start_query_execution.return_value = {"QueryExecutionId": "flow-qid"}
    exec_resp = client.post(
        "/api/v1/queries/execute",
        json={"sql": "SELECT id, name FROM users", "database": "production"},
    )
    assert exec_resp.status_code == 200
    qid = exec_resp.json()["query_execution_id"]

    # Step 2: poll status (SUCCEEDED)
    _stub_execution(mock_svc, qid, state="SUCCEEDED")
    status_resp = client.get(f"/api/v1/queries/{qid}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["state"] == "SUCCEEDED"

    # Step 3: fetch results
    _stub_results(mock_svc, ["id", "name"], [["42", "Bob"]])
    results_resp = client.get(f"/api/v1/queries/{qid}/results")
    assert results_resp.status_code == 200
    assert results_resp.json()["row_count"] == 1


# ── Error cases ───────────────────────────────────────────────────────────────

def test_status_returns_404_for_unknown_query_id():
    client, mock_svc = _make_client()
    mock_svc.get_query_execution.side_effect = Exception("Query not found")

    resp = client.get("/api/v1/queries/unknown-qid/status")

    assert resp.status_code == 404


def test_results_returns_400_on_service_error():
    client, mock_svc = _make_client()
    mock_svc.get_query_results.side_effect = Exception("InvalidRequestException")

    resp = client.get("/api/v1/queries/qid-err/results")

    assert resp.status_code == 400
    # Sanitized response: generic message with a request id, not the raw AWS error.
    assert "InvalidRequestException" not in resp.json()["detail"]
    assert "request_id=" in resp.json()["detail"]


def test_execute_returns_400_on_athena_error():
    client, mock_svc = _make_client()
    mock_svc.start_query_execution.side_effect = Exception("AccessDeniedException")

    resp = client.post(
        "/api/v1/queries/execute",
        json={"sql": "SELECT 1", "database": "mydb"},
    )

    assert resp.status_code == 400
    assert "AccessDeniedException" not in resp.json()["detail"]
    assert "request_id=" in resp.json()["detail"]


def test_failed_query_state_is_reflected_in_status():
    """A FAILED query execution must be surfaced correctly through the status endpoint."""
    client, mock_svc = _make_client()
    _stub_execution(mock_svc, "failed-qid", state="FAILED")

    resp = client.get("/api/v1/queries/failed-qid/status")

    assert resp.status_code == 200
    assert resp.json()["state"] == "FAILED"


def test_results_returns_empty_when_no_rows():
    client, mock_svc = _make_client()
    mock_svc.get_query_results.return_value = {
        "ResultSet": {"Rows": [], "ResultSetMetadata": {"ColumnInfo": []}}
    }

    resp = client.get("/api/v1/queries/empty-qid/results")

    assert resp.status_code == 200
    data = resp.json()
    assert data["row_count"] == 0
    assert data["rows"] == []
