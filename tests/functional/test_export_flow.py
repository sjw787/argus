"""Functional tests: export flow — format validation, access control, content."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from argus.api.app import create_app
from argus.api.dependencies import get_athena_service, get_config
from argus.models.schemas import AppConfig


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_client(allow_download: bool = True) -> tuple[TestClient, MagicMock]:
    app = create_app()
    mock_svc = MagicMock()
    app.dependency_overrides[get_config] = lambda: AppConfig(allow_download=allow_download)
    app.dependency_overrides[get_athena_service] = lambda: mock_svc
    return TestClient(app), mock_svc


def _stub_results(
    mock_svc: MagicMock,
    headers: list[str],
    rows: list[list[str]],
) -> None:
    raw_rows = [{"Data": [{"VarCharValue": h} for h in headers]}]
    for row in rows:
        raw_rows.append({"Data": [{"VarCharValue": v} for v in row]})
    mock_svc.get_query_results.return_value = {
        "ResultSet": {"Rows": raw_rows},
    }


# ── Access control ─────────────────────────────────────────────────────────────

def test_export_blocked_returns_403_when_allow_download_false():
    client, _ = _make_client(allow_download=False)

    resp = client.post("/api/v1/export/abc123", json={"format": "csv"})

    assert resp.status_code == 403
    assert "disabled by the administrator" in resp.json()["detail"]


def test_export_allowed_when_allow_download_true():
    client, mock_svc = _make_client(allow_download=True)
    _stub_results(mock_svc, ["id"], [["1"]])

    resp = client.post("/api/v1/export/abc123", json={"format": "csv"})

    assert resp.status_code == 200


# ── CSV format ────────────────────────────────────────────────────────────────

def test_export_csv_contains_headers_and_rows():
    client, mock_svc = _make_client()
    _stub_results(mock_svc, ["id", "name"], [["1", "Alice"], ["2", "Bob"]])

    resp = client.post("/api/v1/export/abc123", json={"format": "csv"})

    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    assert "id" in body
    assert "name" in body
    assert "Alice" in body
    assert "Bob" in body


def test_export_csv_custom_delimiter():
    client, mock_svc = _make_client()
    _stub_results(mock_svc, ["col_a", "col_b"], [["x", "y"]])

    resp = client.post(
        "/api/v1/export/abc123",
        json={"format": "csv", "delimiter": "|"},
    )

    assert resp.status_code == 200
    assert "|" in resp.text


# ── JSON format ───────────────────────────────────────────────────────────────

def test_export_json_returns_list_of_dicts():
    client, mock_svc = _make_client()
    _stub_results(mock_svc, ["x", "y"], [["1", "2"], ["3", "4"]])

    resp = client.post("/api/v1/export/abc123", json={"format": "json"})

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0] == {"x": "1", "y": "2"}
    assert data[1] == {"x": "3", "y": "4"}


def test_export_json_pretty_flag():
    client, mock_svc = _make_client()
    _stub_results(mock_svc, ["v"], [["42"]])

    resp = client.post(
        "/api/v1/export/abc123",
        json={"format": "json", "pretty": True},
    )

    assert resp.status_code == 200
    # Pretty JSON contains indentation newlines
    assert "\n" in resp.text


# ── Unsupported format ────────────────────────────────────────────────────────

def test_export_unsupported_format_returns_400():
    client, mock_svc = _make_client()
    _stub_results(mock_svc, ["v"], [["1"]])

    resp = client.post("/api/v1/export/abc123", json={"format": "xml"})

    assert resp.status_code == 400


# ── Service error propagation ─────────────────────────────────────────────────

def test_export_returns_400_when_athena_service_raises():
    client, mock_svc = _make_client()
    mock_svc.get_query_results.side_effect = Exception("QueryNotFound")

    resp = client.post("/api/v1/export/bad-qid", json={"format": "csv"})

    assert resp.status_code == 400
    assert "QueryNotFound" not in resp.json()["detail"]
    assert "request_id=" in resp.json()["detail"]
