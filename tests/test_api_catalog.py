from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from athena_beaver.api.app import create_app
from athena_beaver.api.dependencies import get_catalog_service, get_config
from athena_beaver.models.schemas import AppConfig


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


def test_search_databases(client, mock_catalog_svc):
    mock_catalog_svc.search_databases_by_client_id.return_value = [
        {"Name": "client123_prod"}
    ]
    resp = client.get("/api/v1/catalog/search?client_id=client123")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "client123_prod"
