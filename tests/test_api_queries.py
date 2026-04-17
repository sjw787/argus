from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from argus.api.app import create_app
from argus.api.dependencies import get_athena_service, get_config
from argus.models.schemas import AppConfig


@pytest.fixture
def mock_athena_svc():
    return MagicMock()


@pytest.fixture
def client(mock_athena_svc):
    app = create_app()
    app.dependency_overrides[get_config] = lambda: AppConfig()
    app.dependency_overrides[get_athena_service] = lambda: mock_athena_svc
    return TestClient(app)


def test_execute_query(client, mock_athena_svc):
    mock_athena_svc.start_query_execution.return_value = {"QueryExecutionId": "abc-123"}
    resp = client.post("/api/v1/queries/execute", json={"sql": "SELECT 1", "database": "mydb"})
    assert resp.status_code == 200
    assert resp.json()["query_execution_id"] == "abc-123"


def test_get_query(client, mock_athena_svc):
    mock_athena_svc.get_query_execution.return_value = {
        "QueryExecution": {
            "QueryExecutionId": "abc-123",
            "Query": "SELECT 1",
            "Status": {"State": "SUCCEEDED"},
            "Statistics": {},
            "QueryExecutionContext": {"Database": "mydb"},
            "ResultConfiguration": {},
        }
    }
    resp = client.get("/api/v1/queries/abc-123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_execution_id"] == "abc-123"
    assert data["status"]["state"] == "SUCCEEDED"


def test_get_query_results(client, mock_athena_svc):
    mock_athena_svc.get_query_results.return_value = {
        "ResultSet": {
            "Rows": [
                {"Data": [{"VarCharValue": "col1"}, {"VarCharValue": "col2"}]},
                {"Data": [{"VarCharValue": "val1"}, {"VarCharValue": "val2"}]},
            ],
            "ResultSetMetadata": {"ColumnInfo": []},
        }
    }
    resp = client.get("/api/v1/queries/abc-123/results")
    assert resp.status_code == 200
    data = resp.json()
    assert data["row_count"] == 1
    assert data["columns"][0]["name"] == "col1"


def test_cancel_query(client, mock_athena_svc):
    mock_athena_svc.stop_query_execution.return_value = {}
    resp = client.post("/api/v1/queries/abc-123/cancel")
    assert resp.status_code == 200
    assert "cancelled" in resp.json()["message"]


def test_list_queries(client, mock_athena_svc):
    mock_athena_svc.list_query_executions.return_value = {"QueryExecutionIds": ["id-1"]}
    mock_athena_svc.batch_get_query_execution.return_value = {
        "QueryExecutions": [
            {
                "QueryExecutionId": "id-1",
                "Status": {"State": "SUCCEEDED"},
                "QueryExecutionContext": {"Database": "mydb"},
                "WorkGroup": "primary",
            }
        ]
    }
    resp = client.get("/api/v1/queries")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["query_execution_id"] == "id-1"


def test_list_named_queries(client, mock_athena_svc):
    mock_athena_svc.list_named_queries.return_value = {"NamedQueryIds": ["nq-1"]}
    mock_athena_svc.batch_get_named_query.return_value = {
        "NamedQueries": [
            {
                "NamedQueryId": "nq-1",
                "Name": "My Query",
                "Database": "mydb",
                "QueryString": "SELECT 1",
            }
        ]
    }
    resp = client.get("/api/v1/queries/named/list")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "My Query"


def test_create_named_query(client, mock_athena_svc):
    mock_athena_svc.create_named_query.return_value = {"NamedQueryId": "nq-new"}
    resp = client.post(
        "/api/v1/queries/named",
        json={"name": "Test", "sql": "SELECT 1", "database": "mydb"},
    )
    assert resp.status_code == 200
    assert resp.json()["named_query_id"] == "nq-new"


def test_delete_named_query(client, mock_athena_svc):
    mock_athena_svc.delete_named_query.return_value = {}
    resp = client.delete("/api/v1/queries/named/nq-1")
    assert resp.status_code == 200


def test_execute_query_error(client, mock_athena_svc):
    mock_athena_svc.start_query_execution.side_effect = Exception("AccessDenied")
    resp = client.post("/api/v1/queries/execute", json={"sql": "SELECT 1", "database": "mydb"})
    assert resp.status_code == 400
    assert "AccessDenied" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Unit tests for auto-limit helpers
# ---------------------------------------------------------------------------
from argus.api.routers.queries import _has_top_level_limit, _apply_auto_limit

class TestHasTopLevelLimit:
    def test_simple_limit(self):
        assert _has_top_level_limit("SELECT * FROM t LIMIT 100") is True

    def test_no_limit(self):
        assert _has_top_level_limit("SELECT * FROM t") is False

    def test_subquery_limit_only(self):
        # LIMIT is inside subquery — outer has none → should return False
        assert _has_top_level_limit(
            "SELECT * FROM (SELECT id FROM t LIMIT 100)"
        ) is False

    def test_subquery_limit_and_outer_limit(self):
        # Both inner and outer LIMIT
        assert _has_top_level_limit(
            "SELECT * FROM (SELECT id FROM t LIMIT 100) LIMIT 50"
        ) is True

    def test_cte_with_limit_in_cte_only(self):
        sql = "WITH cte AS (SELECT id FROM t LIMIT 100) SELECT * FROM cte"
        assert _has_top_level_limit(sql) is False

    def test_cte_with_outer_limit(self):
        sql = "WITH cte AS (SELECT id FROM t LIMIT 100) SELECT * FROM cte LIMIT 25"
        assert _has_top_level_limit(sql) is True

    def test_limit_in_line_comment_ignored(self):
        sql = "SELECT * FROM t -- LIMIT 10"
        assert _has_top_level_limit(sql) is False

    def test_limit_in_string_literal_ignored(self):
        sql = "SELECT 'LIMIT 999' FROM t"
        assert _has_top_level_limit(sql) is False

    def test_nested_subqueries(self):
        sql = "SELECT * FROM (SELECT * FROM (SELECT id FROM t LIMIT 5) sub) outer_q"
        assert _has_top_level_limit(sql) is False


class TestApplyAutoLimit:
    def test_adds_limit_to_plain_select(self):
        sql, applied = _apply_auto_limit("SELECT * FROM t", 500)
        assert applied is True
        assert "LIMIT 500" in sql

    def test_no_limit_added_when_outer_limit_present(self):
        sql, applied = _apply_auto_limit("SELECT * FROM t LIMIT 10", 500)
        assert applied is False
        assert sql.count("LIMIT") == 1

    def test_adds_limit_when_only_subquery_has_limit(self):
        sql, applied = _apply_auto_limit(
            "SELECT * FROM (SELECT id FROM t LIMIT 100)", 500
        )
        assert applied is True
        assert sql.endswith("LIMIT 500")

    def test_non_select_not_modified(self):
        for stmt in ["INSERT INTO t VALUES (1)", "DROP TABLE t", "CREATE TABLE t (id INT)"]:
            sql, applied = _apply_auto_limit(stmt, 500)
            assert applied is False
            assert sql == stmt

    def test_cte_without_outer_limit(self):
        sql = "WITH cte AS (SELECT id FROM t LIMIT 100) SELECT * FROM cte"
        result, applied = _apply_auto_limit(sql, 500)
        assert applied is True
        assert result.endswith("LIMIT 500")
