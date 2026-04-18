from __future__ import annotations
import pytest
from fastapi.testclient import TestClient

from argus.api.app import create_app
from argus.api.dependencies import get_config
from argus.core.config import save_config, reset_config_cache
from argus.models.schemas import AppConfig, WorkgroupConfig


@pytest.fixture(autouse=True)
def clear_config_cache():
    reset_config_cache()
    yield
    reset_config_cache()


def _make_client(config: AppConfig) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_config] = lambda: config
    return TestClient(app)


def test_get_config_info_returns_expected_fields():
    cfg = AppConfig()
    client = _make_client(cfg)
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["region"] == "us-east-1"
    assert "workgroup_output_locations" in data
    assert "max_results" in data


def test_get_assignments_empty():
    cfg = AppConfig()
    client = _make_client(cfg)
    resp = client.get("/api/v1/config/assignments")
    assert resp.status_code == 200
    assert resp.json() == {"assignments": {}}


def test_get_assignments_populated():
    cfg = AppConfig(workgroups=WorkgroupConfig(assignments={"db1": "wg1"}))
    client = _make_client(cfg)
    resp = client.get("/api/v1/config/assignments")
    assert resp.status_code == 200
    assert resp.json()["assignments"] == {"db1": "wg1"}


def test_assign_database(monkeypatch):
    cfg = AppConfig()
    saved = {}

    def mock_save(c):
        saved["config"] = c

    monkeypatch.setattr("argus.api.routers.config.save_config", mock_save)
    client = _make_client(cfg)
    resp = client.post("/api/v1/config/assignments", json={"database": "mydb", "workgroup": "mywg"})
    assert resp.status_code == 200
    assert resp.json()["assignments"] == {"mydb": "mywg"}
    assert saved["config"].workgroups.assignments == {"mydb": "mywg"}


def test_unassign_database(monkeypatch):
    cfg = AppConfig(workgroups=WorkgroupConfig(assignments={"db1": "wg1", "db2": "wg2"}))
    saved = {}

    def mock_save(c):
        saved["config"] = c

    monkeypatch.setattr("argus.api.routers.config.save_config", mock_save)
    client = _make_client(cfg)
    resp = client.delete("/api/v1/config/assignments/db1")
    assert resp.status_code == 200
    assert "db1" not in resp.json()["assignments"]
    assert "db2" in resp.json()["assignments"]
