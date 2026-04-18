"""Tests for src/argus/core/audit_logger.py and AuditMiddleware."""
from __future__ import annotations

import importlib
import json
import sys
from unittest.mock import MagicMock, patch

import pytest


def _reload_audit_logger():
    for mod in ("argus.core.audit_logger",):
        if mod in sys.modules:
            del sys.modules[mod]
    return importlib.import_module("argus.core.audit_logger")


# ── AuditLogger unit tests ────────────────────────────────────────────────────

class TestAuditLoggerDisabled:
    def test_no_op_when_disabled(self, monkeypatch):
        monkeypatch.delenv("ARGUS_AUDIT_LOGGING", raising=False)
        m = _reload_audit_logger()
        logger = m.AuditLogger()
        assert logger._enabled is False

    def test_log_action_is_no_op_when_disabled(self, monkeypatch):
        monkeypatch.delenv("ARGUS_AUDIT_LOGGING", raising=False)
        m = _reload_audit_logger()
        logger = m.AuditLogger()
        # Should not raise, no side-effects
        logger.log_action(
            user_identity="alice",
            action_type="QUERY_EXECUTE",
            http_method="POST",
            path="/api/v1/queries/execute",
            status_code=200,
            duration_ms=42.0,
        )


class TestAuditLoggerEnabled:
    def test_enabled_when_env_var_set(self, monkeypatch):
        monkeypatch.setenv("ARGUS_AUDIT_LOGGING", "true")
        monkeypatch.setenv("ARGUS_AUDIT_LOG_GROUP", "")
        m = _reload_audit_logger()
        logger = m.AuditLogger()
        assert logger._enabled is True

    @pytest.mark.parametrize("val", ["true", "1", "yes"])
    def test_truthy_env_values_enable(self, monkeypatch, val):
        monkeypatch.setenv("ARGUS_AUDIT_LOGGING", val)
        monkeypatch.setenv("ARGUS_AUDIT_LOG_GROUP", "")
        m = _reload_audit_logger()
        logger = m.AuditLogger()
        assert logger._enabled is True

    def test_log_action_emits_to_application_log_when_no_log_group(self, monkeypatch):
        monkeypatch.setenv("ARGUS_AUDIT_LOGGING", "true")
        monkeypatch.setenv("ARGUS_AUDIT_LOG_GROUP", "")  # No CW group configured
        m = _reload_audit_logger()
        logger = m.AuditLogger()
        with patch.object(logger, "_emit") as mock_emit:
            logger.log_action(
                user_identity="bob",
                action_type="CATALOG_READ",
                http_method="GET",
                path="/api/v1/catalog/databases",
                status_code=200,
                duration_ms=15.5,
            )
        mock_emit.assert_called_once()
        record = mock_emit.call_args[0][0]  # _emit receives the dict directly
        assert record["user_identity"] == "bob"
        assert record["action_type"] == "CATALOG_READ"
        assert record["status_code"] == 200
        assert record["http_method"] == "GET"
        assert record["path"] == "/api/v1/catalog/databases"
        assert "duration_ms" in record
        assert "timestamp" in record

    def test_log_action_includes_optional_fields(self, monkeypatch):
        monkeypatch.setenv("ARGUS_AUDIT_LOGGING", "true")
        monkeypatch.setenv("ARGUS_AUDIT_LOG_GROUP", "")
        m = _reload_audit_logger()
        logger = m.AuditLogger()
        with patch.object(logger, "_emit") as mock_emit:
            logger.log_action(
                user_identity="carol",
                action_type="QUERY_EXECUTE",
                http_method="POST",
                path="/api/v1/queries/execute",
                status_code=202,
                duration_ms=99.9,
                database="prod_db",
                workgroup="prod_wg",
                execution_id="qe-12345",
                request_id="req-abc",
            )
        record = mock_emit.call_args[0][0]
        assert record["database"] == "prod_db"
        assert record["workgroup"] == "prod_wg"
        assert record["execution_id"] == "qe-12345"
        assert record["request_id"] == "req-abc"

    def test_log_action_omits_none_optional_fields(self, monkeypatch):
        """None optional fields must not appear in the record (GDPR/privacy)."""
        monkeypatch.setenv("ARGUS_AUDIT_LOGGING", "true")
        monkeypatch.setenv("ARGUS_AUDIT_LOG_GROUP", "")
        m = _reload_audit_logger()
        logger = m.AuditLogger()
        with patch.object(logger, "_emit") as mock_emit:
            logger.log_action(
                user_identity="dave",
                action_type="EXPORT",
                http_method="GET",
                path="/api/v1/export",
                status_code=200,
                duration_ms=1.0,
            )
        record = mock_emit.call_args[0][0]
        assert "database" not in record
        assert "workgroup" not in record
        assert "execution_id" not in record

    def test_never_logs_sql_or_result_data(self, monkeypatch):
        """Critical privacy requirement: SQL text and result data must never appear in logs."""
        monkeypatch.setenv("ARGUS_AUDIT_LOGGING", "true")
        monkeypatch.setenv("ARGUS_AUDIT_LOG_GROUP", "")
        m = _reload_audit_logger()
        logger = m.AuditLogger()
        emitted: list[dict] = []
        with patch.object(logger, "_emit", side_effect=lambda rec: emitted.append(rec)):
            logger.log_action(
                user_identity="eve",
                action_type="QUERY_EXECUTE",
                http_method="POST",
                path="/api/v1/queries/execute",
                status_code=200,
                duration_ms=50.0,
                database="secret_db",
            )
        assert len(emitted) == 1
        record = emitted[0]
        # Verify the record fields — there should be no 'query', 'sql', 'results', 'rows'
        disallowed = {"query", "sql", "results", "rows", "data", "columns"}
        for field in disallowed:
            assert field not in record, f"Field '{field}' must not appear in audit log"


# ── _classify_action tests ────────────────────────────────────────────────────

class TestClassifyAction:
    @pytest.mark.parametrize("method,path,expected", [
        ("POST",   "/api/v1/queries/execute",          "QUERY_EXECUTE"),
        ("POST",   "/api/v1/explain",                  "EXPLAIN"),
        ("GET",    "/api/v1/export",                   "EXPORT"),
        ("POST",   "/api/v1/auth/login",               "LOGIN"),
        ("POST",   "/api/v1/auth/logout",              "LOGOUT"),
        ("PUT",    "/api/v1/config",                   "CONFIG_CHANGE"),
        ("PATCH",  "/api/v1/config",                   "CONFIG_CHANGE"),
        ("GET",    "/api/v1/catalog/databases",        "CATALOG_READ"),
        ("GET",    "/api/v1/workgroups",               "OTHER"),
        ("GET",    "/api/v1/queries/abc/status",       "OTHER"),
    ])
    def test_action_classification(self, method, path, expected):
        from argus.core.audit_logger import _classify_action
        result = _classify_action(method, path)
        assert result == expected


# ── AuditMiddleware integration tests ─────────────────────────────────────────

class TestAuditMiddleware:
    def test_middleware_calls_log_action_when_enabled(self, monkeypatch):
        monkeypatch.setenv("ARGUS_AUDIT_LOGGING", "true")
        monkeypatch.setenv("ARGUS_AUDIT_LOG_GROUP", "")
        monkeypatch.delenv("LAMBDA_RUNTIME", raising=False)

        from fastapi.testclient import TestClient
        from argus.api.app import create_app
        # Reference the audit_logger object through the middleware module —
        # this is the exact object the middleware calls log_action on,
        # regardless of any module reloads in other tests.
        import argus.api.middleware as _mw_module

        calls: list[dict] = []
        original_log = _mw_module.audit_logger.log_action
        original_enabled = _mw_module.audit_logger._enabled

        def capture(**kwargs):
            calls.append(kwargs)

        _mw_module.audit_logger._enabled = True
        _mw_module.audit_logger.log_action = capture  # type: ignore[method-assign]

        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            client.get("/api/v1/config")
        finally:
            _mw_module.audit_logger.log_action = original_log
            _mw_module.audit_logger._enabled = original_enabled

        assert len(calls) >= 1
        call = calls[0]
        assert call["http_method"] == "GET"
        assert "/api/v1/config" in call["path"]
        assert "status_code" in call
        assert "duration_ms" in call

    def test_middleware_no_op_when_disabled(self, monkeypatch):
        monkeypatch.delenv("ARGUS_AUDIT_LOGGING", raising=False)
        monkeypatch.delenv("LAMBDA_RUNTIME", raising=False)

        from fastapi.testclient import TestClient
        from argus.api.app import create_app
        import argus.api.middleware as _mw_module

        original_enabled = _mw_module.audit_logger._enabled
        _mw_module.audit_logger._enabled = False

        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/api/v1/config")
        finally:
            _mw_module.audit_logger._enabled = original_enabled

        assert response.status_code in (200, 401, 403, 422)
