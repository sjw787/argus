from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from argus.api.app import create_app
from argus.api.dependencies import get_athena_service, get_config
from argus.models.schemas import AppConfig


def _make_client(allow_download: bool = True) -> tuple[TestClient, MagicMock]:
    app = create_app()
    mock_svc = MagicMock()
    app.dependency_overrides[get_config] = lambda: AppConfig(allow_download=allow_download)
    app.dependency_overrides[get_athena_service] = lambda: mock_svc
    return TestClient(app), mock_svc


def _stub_results(mock_svc, headers: list[str], rows: list[list[str]]):
    raw_rows = [{"Data": [{"VarCharValue": h} for h in headers]}]
    for row in rows:
        raw_rows.append({"Data": [{"VarCharValue": v} for v in row]})
    mock_svc.get_query_results.return_value = {"ResultSet": {"Rows": raw_rows}}


def test_export_blocked_when_allow_download_false():
    client, _ = _make_client(allow_download=False)
    resp = client.post("/api/v1/export/abc123", json={"format": "csv"})
    assert resp.status_code == 403
    assert "disabled by the administrator" in resp.json()["detail"]


def test_export_csv_allowed_by_default():
    client, mock_svc = _make_client(allow_download=True)
    _stub_results(mock_svc, ["id", "name"], [["1", "Alice"], ["2", "Bob"]])
    resp = client.post("/api/v1/export/abc123", json={"format": "csv"})
    assert resp.status_code == 200
    assert "id" in resp.text
    assert "Alice" in resp.text


def test_export_json_allowed():
    client, mock_svc = _make_client(allow_download=True)
    _stub_results(mock_svc, ["x"], [["42"]])
    resp = client.post("/api/v1/export/abc123", json={"format": "json"})
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["x"] == "42"


def test_export_invalid_format():
    client, mock_svc = _make_client()
    _stub_results(mock_svc, ["x"], [["1"]])
    resp = client.post("/api/v1/export/abc123", json={"format": "xml"})
    assert resp.status_code == 400
