from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from athena_beaver.services.athena_service import AthenaService
from athena_beaver.models.schemas import AppConfig, NamingSchema, WorkgroupConfig, DefaultsConfig


@pytest.fixture
def config_with_schema():
    return AppConfig(
        naming_schemas={
            "default": NamingSchema(
                pattern="{purpose}_{client_id}_{environment}",
                client_id_regex=r"\d{6}|\d{9}",
                workgroup_pattern="{purpose}_{client_id}_{environment}",
            )
        },
        active_schema="default",
        workgroups=WorkgroupConfig(
            output_locations={
                "analytics_123456_prod": "s3://results/123456/prod/",
            },
            assignments={
                "analytics_123456_prod": "analytics_123456_prod",
            },
        ),
        defaults=DefaultsConfig(output_location="s3://results/default/"),
    )


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def service(mock_client, config_with_schema):
    return AthenaService(mock_client, config_with_schema)


class TestStartQueryExecution:
    def test_auto_resolves_workgroup(self, service, mock_client):
        mock_client.start_query_execution.return_value = {"QueryExecutionId": "qid-1"}
        service.start_query_execution("SELECT 1", "analytics_123456_prod")
        mock_client.start_query_execution.assert_called_once()
        call_kwargs = mock_client.start_query_execution.call_args[1]
        assert call_kwargs["WorkGroup"] == "analytics_123456_prod"

    def test_auto_resolves_s3_output_from_config(self, service, mock_client):
        mock_client.start_query_execution.return_value = {"QueryExecutionId": "qid-1"}
        service.start_query_execution("SELECT 1", "analytics_123456_prod")
        call_kwargs = mock_client.start_query_execution.call_args[1]
        assert call_kwargs["ResultConfiguration"]["OutputLocation"] == "s3://results/123456/prod/"

    def test_uses_default_output_when_no_workgroup_match(self, service, mock_client):
        mock_client.start_query_execution.return_value = {"QueryExecutionId": "qid-1"}
        service.start_query_execution("SELECT 1", "analytics_999999_prod")
        call_kwargs = mock_client.start_query_execution.call_args[1]
        assert call_kwargs["ResultConfiguration"]["OutputLocation"] == "s3://results/default/"

    def test_override_workgroup(self, service, mock_client):
        mock_client.start_query_execution.return_value = {"QueryExecutionId": "qid-1"}
        service.start_query_execution("SELECT 1", "analytics_123456_prod", workgroup="custom-wg")
        call_kwargs = mock_client.start_query_execution.call_args[1]
        assert call_kwargs["WorkGroup"] == "custom-wg"

    def test_override_output_location(self, service, mock_client):
        mock_client.start_query_execution.return_value = {"QueryExecutionId": "qid-1"}
        service.start_query_execution(
            "SELECT 1", "analytics_123456_prod", output_location="s3://custom/"
        )
        call_kwargs = mock_client.start_query_execution.call_args[1]
        assert call_kwargs["ResultConfiguration"]["OutputLocation"] == "s3://custom/"


class TestWaitForQuery:
    def test_returns_on_succeeded(self, service, mock_client):
        mock_client.get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "SUCCEEDED"}}
        }
        result = service.wait_for_query("qid-1", poll_interval=0)
        assert result["QueryExecution"]["Status"]["State"] == "SUCCEEDED"

    def test_raises_on_timeout(self, service, mock_client):
        mock_client.get_query_execution.return_value = {
            "QueryExecution": {"Status": {"State": "RUNNING"}}
        }
        with pytest.raises(TimeoutError):
            service.wait_for_query("qid-1", poll_interval=0, timeout=0.001)
