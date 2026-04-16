from __future__ import annotations
import pytest
from athena_beaver.core.naming import NamingResolver, _compile_pattern, get_resolver
from athena_beaver.models.schemas import NamingSchema


@pytest.fixture
def default_schema():
    return NamingSchema(
        pattern="{purpose}_{client_id}_{environment}",
        client_id_regex=r"\d{6}|\d{9}",
        workgroup_pattern="{purpose}_{client_id}_{environment}",
    )


@pytest.fixture
def short_schema():
    return NamingSchema(
        pattern="{client_id}_{purpose}",
        client_id_regex=r"[a-z]{3}\d{4}",
        workgroup_pattern="wg_{client_id}",
    )


class TestNamingResolver:
    def test_parse_six_digit_client_id(self, default_schema):
        r = NamingResolver(default_schema)
        parts = r.parse_database_name("analytics_123456_prod")
        assert parts == {"purpose": "analytics", "client_id": "123456", "environment": "prod"}

    def test_parse_nine_digit_client_id(self, default_schema):
        r = NamingResolver(default_schema)
        parts = r.parse_database_name("reporting_123456789_dev")
        assert parts == {"purpose": "reporting", "client_id": "123456789", "environment": "dev"}

    def test_parse_no_match_returns_none(self, default_schema):
        r = NamingResolver(default_schema)
        assert r.parse_database_name("not_a_valid_name") is None

    def test_resolve_workgroup_standard(self, default_schema):
        r = NamingResolver(default_schema, assignments={"analytics_123456_prod": "analytics_123456_prod"})
        wg = r.resolve_workgroup("analytics_123456_prod")
        assert wg == "analytics_123456_prod"

    def test_resolve_workgroup_no_match(self, default_schema):
        r = NamingResolver(default_schema)
        assert r.resolve_workgroup("bad_name") is None

    def test_get_client_id(self, default_schema):
        r = NamingResolver(default_schema)
        assert r.get_client_id("analytics_123456_prod") == "123456"

    def test_short_schema_parse(self, short_schema):
        r = NamingResolver(short_schema)
        parts = r.parse_database_name("abc1234_reports")
        assert parts == {"client_id": "abc1234", "purpose": "reports"}

    def test_short_schema_workgroup(self, short_schema):
        r = NamingResolver(short_schema, assignments={"abc1234_reports": "wg_abc1234"})
        assert r.resolve_workgroup("abc1234_reports") == "wg_abc1234"

    def test_get_resolver_returns_none_for_missing_schema(self, sample_config):
        resolver = get_resolver(sample_config, "nonexistent")
        assert resolver is None

    def test_get_resolver_uses_active_schema(self, sample_config):
        resolver = get_resolver(sample_config)
        assert resolver is not None
        # resolve_workgroup is now assignment-only; no assignment means None
        assert resolver.resolve_workgroup("analytics_123456_prod") is None


@pytest.fixture
def sample_config():
    from athena_beaver.models.schemas import AppConfig, NamingSchema, AWSConfig
    return AppConfig(
        aws=AWSConfig(region="us-east-1"),
        naming_schemas={
            "default": NamingSchema(
                pattern="{purpose}_{client_id}_{environment}",
                client_id_regex=r"\d{6}|\d{9}",
                workgroup_pattern="{purpose}_{client_id}_{environment}",
            ),
        },
        active_schema="default",
    )
