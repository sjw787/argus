from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from athena_beaver.api.app import create_app
from athena_beaver.api.dependencies import get_workgroup_service, get_config
from athena_beaver.models.schemas import AppConfig, NamingSchema, WorkgroupConfig


@pytest.fixture
def mock_wg_svc():
    return MagicMock()


@pytest.fixture
def client(mock_wg_svc):
    app = create_app()
    app.dependency_overrides[get_config] = lambda: AppConfig()
    app.dependency_overrides[get_workgroup_service] = lambda: mock_wg_svc
    return TestClient(app)


def test_list_workgroups(client, mock_wg_svc):
    mock_wg_svc.list_work_groups.return_value = {
        "WorkGroups": [{"Name": "primary", "State": "ENABLED"}]
    }
    mock_wg_svc.get_work_group.return_value = {
        "WorkGroup": {
            "Name": "primary",
            "State": "ENABLED",
            "Configuration": {"ResultConfiguration": {}, "EngineVersion": {}},
        }
    }
    resp = client.get("/api/v1/workgroups")
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "primary"


def test_get_workgroup(client, mock_wg_svc):
    mock_wg_svc.get_work_group.return_value = {
        "WorkGroup": {
            "Name": "primary",
            "State": "ENABLED",
            "Configuration": {
                "ResultConfiguration": {"OutputLocation": "s3://bucket/"},
                "EngineVersion": {"SelectedEngineVersion": "Athena engine version 3"},
            },
        }
    }
    resp = client.get("/api/v1/workgroups/primary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "primary"
    assert data["output_location"] == "s3://bucket/"


def test_get_workgroup_not_found(client, mock_wg_svc):
    mock_wg_svc.get_work_group.side_effect = Exception("WorkGroup not found")
    resp = client.get("/api/v1/workgroups/missing")
    assert resp.status_code == 404


def test_create_workgroup(client, mock_wg_svc):
    mock_wg_svc.create_work_group.return_value = {}
    resp = client.post(
        "/api/v1/workgroups",
        json={"name": "new-wg", "output_location": "s3://bucket/"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "new-wg"


def test_delete_workgroup(client, mock_wg_svc):
    mock_wg_svc.delete_work_group.return_value = {}
    resp = client.delete("/api/v1/workgroups/primary")
    assert resp.status_code == 200
    assert "deleted" in resp.json()["message"]


def test_update_workgroup(client, mock_wg_svc):
    mock_wg_svc.update_work_group.return_value = {}
    mock_wg_svc.get_work_group.return_value = {
        "WorkGroup": {
            "Name": "primary",
            "State": "ENABLED",
            "Configuration": {"ResultConfiguration": {}, "EngineVersion": {}},
        }
    }
    resp = client.put("/api/v1/workgroups/primary", json={"description": "Updated"})
    assert resp.status_code == 200


def test_resolve_workgroup_no_schema(client):
    resp = client.get("/api/v1/workgroups/resolve/mydb")
    assert resp.status_code == 200
    data = resp.json()
    assert data["database"] == "mydb"
    assert data["matched"] is False


def test_resolve_workgroup_with_schema():
    config = AppConfig(
        naming_schemas={
            "default": NamingSchema(
                pattern="{client_id}_prod",
                client_id_regex=r"[a-z0-9]+",
                workgroup_pattern="{client_id}-wg",
            )
        },
        active_schema="default",
        workgroups=WorkgroupConfig(assignments={"acme_prod": "acme-wg"}),
    )
    app = create_app()
    app.dependency_overrides[get_config] = lambda: config
    app.dependency_overrides[get_workgroup_service] = lambda: MagicMock()
    with TestClient(app) as c:
        resp = c.get("/api/v1/workgroups/resolve/acme_prod")
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched"] is True
    assert data["workgroup"] == "acme-wg"
