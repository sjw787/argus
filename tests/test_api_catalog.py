from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from argus.api.app import create_app
from argus.api.dependencies import get_catalog_service, get_config
from argus.api.routers.catalog import _db_cache
from argus.models.schemas import AppConfig, WorkgroupConfig


@pytest.fixture(autouse=True)
def clear_db_cache():
    """Flush the module-level database list cache before every catalog test."""
    _db_cache.invalidate_all()
    yield
    _db_cache.invalidate_all()


@pytest.fixture
def mock_catalog_svc():
    return MagicMock()


@pytest.fixture
def client(mock_catalog_svc):
    app = create_app()
    app.dependency_overrides[get_config] = lambda: AppConfig()
    app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_svc
    return TestClient(app)


def test_list_databases(client, mock_catalog_svc):
    mock_catalog_svc.list_databases.return_value = {
        "DatabaseList": [{"Name": "mydb", "Description": "test db"}]
    }
    resp = client.get("/api/v1/catalog/databases")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["name"] == "mydb"


# ---------------------------------------------------------------------------
# Workgroup annotation in list_databases
# ---------------------------------------------------------------------------

def test_list_databases_shows_assigned_workgroup(mock_catalog_svc):
    """Databases with an explicit assignment should have their workgroup returned."""
    config = AppConfig(
        workgroups=WorkgroupConfig(assignments={"acme_prod": "acme-wg"}),
    )
    app = create_app()
    app.dependency_overrides[get_config] = lambda: config
    app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_svc
    mock_catalog_svc.list_databases.return_value = {
        "DatabaseList": [{"Name": "acme_prod"}]
    }
    with TestClient(app) as c:
        resp = c.get("/api/v1/catalog/databases")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["workgroup"] == "acme-wg"


def test_list_databases_unassigned_workgroup_is_none(mock_catalog_svc):
    """Databases not in the assignment map should have workgroup=None."""
    config = AppConfig(
        workgroups=WorkgroupConfig(assignments={}),  # no assignments
    )
    app = create_app()
    app.dependency_overrides[get_config] = lambda: config
    app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_svc
    mock_catalog_svc.list_databases.return_value = {
        "DatabaseList": [{"Name": "other_prod"}]
    }
    with TestClient(app) as c:
        resp = c.get("/api/v1/catalog/databases")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["workgroup"] is None


def test_list_databases_no_schema_workgroup_is_none(mock_catalog_svc):
    """With no naming schema configured, the workgroup field should be None."""
    config = AppConfig()  # no schemas, no assignments
    app = create_app()
    app.dependency_overrides[get_config] = lambda: config
    app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_svc
    mock_catalog_svc.list_databases.return_value = {
        "DatabaseList": [{"Name": "mydb"}]
    }
    with TestClient(app) as c:
        resp = c.get("/api/v1/catalog/databases")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["workgroup"] is None


def test_list_databases_multiple_mixed_assignments(mock_catalog_svc):
    """Only assigned databases carry a workgroup; unassigned ones stay None."""
    config = AppConfig(
        workgroups=WorkgroupConfig(assignments={"assigned_prod": "assigned-wg"}),
    )
    app = create_app()
    app.dependency_overrides[get_config] = lambda: config
    app.dependency_overrides[get_catalog_service] = lambda: mock_catalog_svc
    mock_catalog_svc.list_databases.return_value = {
        "DatabaseList": [
            {"Name": "assigned_prod"},
            {"Name": "unassigned_prod"},
        ]
    }
    with TestClient(app) as c:
        resp = c.get("/api/v1/catalog/databases")
    items = {item["name"]: item for item in resp.json()["items"]}
    assert items["assigned_prod"]["workgroup"] == "assigned-wg"
    assert items["unassigned_prod"]["workgroup"] is None

def test_get_database(client, mock_catalog_svc):
    mock_catalog_svc.get_database.return_value = {
        "Database": {"Name": "mydb", "Description": "test db"}
    }
    resp = client.get("/api/v1/catalog/databases/mydb")
    assert resp.status_code == 200
    assert resp.json()["name"] == "mydb"


def test_get_database_not_found(client, mock_catalog_svc):
    mock_catalog_svc.get_database.side_effect = Exception("EntityNotFoundException")
    resp = client.get("/api/v1/catalog/databases/missing")
    assert resp.status_code == 404


def test_create_database(client, mock_catalog_svc):
    mock_catalog_svc.create_database.return_value = {}
    resp = client.post("/api/v1/catalog/databases", json={"name": "newdb"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "newdb"


def test_delete_database(client, mock_catalog_svc):
    mock_catalog_svc.delete_database.return_value = {}
    resp = client.delete("/api/v1/catalog/databases/mydb")
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"]


def test_list_tables(client, mock_catalog_svc):
    mock_catalog_svc.list_tables.return_value = {
        "TableList": [
            {"Name": "orders", "TableType": "EXTERNAL_TABLE", "StorageDescriptor": {}}
        ]
    }
    resp = client.get("/api/v1/catalog/databases/mydb/tables")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "orders"


def test_get_table(client, mock_catalog_svc):
    mock_catalog_svc.get_table.return_value = {
        "Table": {
            "Name": "orders",
            "TableType": "EXTERNAL_TABLE",
            "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]},
            "PartitionKeys": [],
        }
    }
    resp = client.get("/api/v1/catalog/databases/mydb/tables/orders")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "orders"
    assert data["columns"][0]["name"] == "id"


def test_delete_table(client, mock_catalog_svc):
    mock_catalog_svc.delete_table.return_value = {}
    resp = client.delete("/api/v1/catalog/databases/mydb/tables/orders")
    assert resp.status_code == 200


def test_list_partitions(client, mock_catalog_svc):
    mock_catalog_svc.get_partitions.return_value = {
        "Partitions": [
            {"Values": ["2024-01-01"], "StorageDescriptor": {"Location": "s3://bucket/p=1"}}
        ]
    }
    resp = client.get("/api/v1/catalog/databases/mydb/tables/orders/partitions")
    assert resp.status_code == 200
    assert resp.json()[0]["values"] == ["2024-01-01"]


def test_er_diagram(client, mock_catalog_svc):
    mock_catalog_svc.list_tables.return_value = {
        "TableList": [
            {
                "Name": "orders",
                "StorageDescriptor": {
                    "Columns": [{"Name": "id", "Type": "bigint"}, {"Name": "user_id", "Type": "bigint"}]
                },
                "PartitionKeys": [],
            },
            {
                "Name": "user",
                "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "bigint"}]},
                "PartitionKeys": [],
            },
        ]
    }
    resp = client.get("/api/v1/catalog/databases/mydb/er-diagram")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 2
    # user_id in orders should create edge to user
    assert any(e["source_column"] == "user_id" for e in data["edges"])
