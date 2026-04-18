"""Tests for src/argus/services/aws_endpoints.py."""
from __future__ import annotations

import importlib
import os
import sys

import pytest


def _reload_module():
    """Reload aws_endpoints so it picks up env-var changes made in tests."""
    mod_name = "argus.services.aws_endpoints"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


class TestFipsEnabled:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("ARGUS_USE_FIPS_ENDPOINTS", raising=False)
        m = _reload_module()
        assert m.fips_enabled() is False

    @pytest.mark.parametrize("val", ["true", "True", "TRUE", "1", "yes"])
    def test_truthy_values_enable_fips(self, monkeypatch, val):
        monkeypatch.setenv("ARGUS_USE_FIPS_ENDPOINTS", val)
        m = _reload_module()
        assert m.fips_enabled() is True

    @pytest.mark.parametrize("val", ["false", "0", "no", ""])
    def test_falsy_values_keep_fips_disabled(self, monkeypatch, val):
        monkeypatch.setenv("ARGUS_USE_FIPS_ENDPOINTS", val)
        m = _reload_module()
        assert m.fips_enabled() is False


class TestGetEndpointUrl:
    def test_returns_none_when_fips_disabled(self, monkeypatch):
        monkeypatch.delenv("ARGUS_USE_FIPS_ENDPOINTS", raising=False)
        m = _reload_module()
        assert m.get_endpoint_url("athena", "us-east-1") is None

    def test_returns_none_for_unknown_service_when_enabled(self, monkeypatch):
        monkeypatch.setenv("ARGUS_USE_FIPS_ENDPOINTS", "true")
        m = _reload_module()
        assert m.get_endpoint_url("sagemaker", "us-east-1") is None

    @pytest.mark.parametrize("service,expected_host", [
        ("athena",   "athena-fips.us-east-1.amazonaws.com"),
        ("glue",     "glue-fips.us-east-1.amazonaws.com"),
        ("s3",       "s3-fips.us-east-1.amazonaws.com"),
        ("sts",      "sts-fips.us-east-1.amazonaws.com"),
        ("logs",     "logs-fips.us-east-1.amazonaws.com"),
        ("sso",      "portal.sso-fips.us-east-1.amazonaws.com"),
        ("sso-oidc", "oidc-fips.us-east-1.amazonaws.com"),
    ])
    def test_fips_endpoints_for_known_services(self, monkeypatch, service, expected_host):
        monkeypatch.setenv("ARGUS_USE_FIPS_ENDPOINTS", "true")
        m = _reload_module()
        url = m.get_endpoint_url(service, "us-east-1")
        assert url == f"https://{expected_host}"

    def test_region_interpolated_correctly(self, monkeypatch):
        monkeypatch.setenv("ARGUS_USE_FIPS_ENDPOINTS", "true")
        m = _reload_module()
        url = m.get_endpoint_url("athena", "us-gov-west-1")
        assert url == "https://athena-fips.us-gov-west-1.amazonaws.com"

    def test_url_is_https(self, monkeypatch):
        monkeypatch.setenv("ARGUS_USE_FIPS_ENDPOINTS", "true")
        m = _reload_module()
        for svc in ("athena", "glue", "s3", "sts", "logs", "sso", "sso-oidc"):
            url = m.get_endpoint_url(svc, "us-east-1")
            assert url is not None
            assert url.startswith("https://")
