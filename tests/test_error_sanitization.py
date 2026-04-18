"""Tests for the sanitize_error helper."""
from __future__ import annotations

import logging

import pytest

from argus.api.errors import sanitize_error


def test_sanitize_error_hides_raw_exception_from_client(caplog):
    try:
        raise RuntimeError("AWS AccessDeniedException: secret-bucket-name")
    except RuntimeError as exc:
        with caplog.at_level(logging.ERROR, logger="argus.api.errors"):
            http_exc = sanitize_error(exc, status_code=400, public_message="Catalog failed")

    assert http_exc.status_code == 400
    assert "Catalog failed" in http_exc.detail
    assert "request_id=" in http_exc.detail
    assert "secret-bucket-name" not in http_exc.detail
    assert "AccessDenied" not in http_exc.detail
    # But the full exception IS logged server-side.
    assert "secret-bucket-name" in caplog.text
    assert "AccessDenied" in caplog.text


def test_sanitize_error_verbose_mode_includes_raw_message(monkeypatch, caplog):
    monkeypatch.setenv("ARGUS_VERBOSE_ERRORS", "true")
    try:
        raise ValueError("boom")
    except ValueError as exc:
        with caplog.at_level(logging.ERROR, logger="argus.api.errors"):
            http_exc = sanitize_error(exc, status_code=500, public_message="Oops")
    assert "boom" in http_exc.detail
    assert "request_id=" in http_exc.detail


def test_sanitize_error_default_status():
    try:
        raise Exception("x")
    except Exception as exc:
        http_exc = sanitize_error(exc)
    assert http_exc.status_code == 400
    assert "Request failed" in http_exc.detail


@pytest.mark.parametrize("val", ["1", "true", "YES"])
def test_verbose_error_env_truthy(monkeypatch, val):
    monkeypatch.setenv("ARGUS_VERBOSE_ERRORS", val)
    try:
        raise Exception("detail-str")
    except Exception as exc:
        http_exc = sanitize_error(exc)
    assert "detail-str" in http_exc.detail
