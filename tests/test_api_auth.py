from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from argus.api.app import create_app
from argus.api.dependencies import get_config
from argus.models.schemas import AppConfig


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_config] = lambda: AppConfig()
    return TestClient(app)


# ── /auth/config ──────────────────────────────────────────────────────────────

def test_auth_config_defaults(client):
    resp = client.get("/api/v1/auth/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "sso"
    assert "streaming" in data


# ── /auth/status: credential_id fast-path ────────────────────────────────────

def test_auth_status_with_valid_credential_id(client):
    """Valid X-Credential-Id in DynamoDB session → authenticated without profile check."""
    session_data = {"profile": "test-profile", "region": "us-east-1"}
    with patch("argus.api.routers.auth.get_session", return_value=session_data):
        resp = client.get("/api/v1/auth/status", headers={"X-Credential-Id": "cred-abc"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert data["profile"] == "test-profile"


def test_auth_status_with_expired_credential_id(client):
    """Expired/unknown X-Credential-Id falls back to profile check."""
    with patch("argus.api.routers.auth.get_session", return_value=None), \
         patch("argus.services.sso_service.SsoService.check_credentials", return_value=False), \
         patch("argus.services.sso_service.SsoService.list_profiles", return_value=[]):
        resp = client.get("/api/v1/auth/status", headers={"X-Credential-Id": "expired-cred"})
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False


def test_auth_status_no_credential_id_unauthenticated(client):
    """No credential header + no local creds → unauthenticated."""
    with patch("argus.services.sso_service.SsoService.check_credentials", return_value=False), \
         patch("argus.services.sso_service.SsoService.list_profiles", return_value=[]):
        resp = client.get("/api/v1/auth/status")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False


def test_auth_status_no_credential_id_authenticated_locally(client):
    """No credential header but local creds resolve → authenticated (local dev mode)."""
    with patch("argus.services.sso_service.SsoService.check_credentials", return_value=True), \
         patch("argus.services.sso_service.SsoService.list_profiles", return_value=["default"]):
        resp = client.get("/api/v1/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert "default" in data["profiles"]
