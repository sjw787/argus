from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from argus.services.athena_service import AthenaService
from argus.models.schemas import AppConfig, WorkgroupConfig, DefaultsConfig


@pytest.fixture
def config_with_schema():
    return AppConfig(
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


class TestQueryHelpers:
    def test_stop_query_execution(self, service, mock_client):
        mock_client.stop_query_execution.return_value = {}
        service.stop_query_execution("qid-1")
        mock_client.stop_query_execution.assert_called_once_with(QueryExecutionId="qid-1")

    def test_get_query_execution(self, service, mock_client):
        mock_client.get_query_execution.return_value = {"QueryExecution": {}}
        service.get_query_execution("qid-1")
        mock_client.get_query_execution.assert_called_once_with(QueryExecutionId="qid-1")

    def test_get_query_results(self, service, mock_client):
        mock_client.get_query_results.return_value = {"ResultSet": {}}
        service.get_query_results("qid-1")
        mock_client.get_query_results.assert_called_once_with(QueryExecutionId="qid-1")

    def test_get_query_results_with_params(self, service, mock_client):
        mock_client.get_query_results.return_value = {"ResultSet": {}}
        service.get_query_results("qid-1", max_results=100, next_token="tok")
        mock_client.get_query_results.assert_called_once_with(
            QueryExecutionId="qid-1", MaxResults=100, NextToken="tok"
        )

    def test_list_query_executions(self, service, mock_client):
        mock_client.list_query_executions.return_value = {"QueryExecutionIds": []}
        service.list_query_executions()
        mock_client.list_query_executions.assert_called_once_with()

    def test_list_query_executions_with_params(self, service, mock_client):
        mock_client.list_query_executions.return_value = {"QueryExecutionIds": []}
        service.list_query_executions(workgroup="wg1", max_results=5, next_token="t")
        mock_client.list_query_executions.assert_called_once_with(
            WorkGroup="wg1", MaxResults=5, NextToken="t"
        )

    def test_batch_get_query_execution(self, service, mock_client):
        mock_client.batch_get_query_execution.return_value = {"QueryExecutions": []}
        service.batch_get_query_execution(["q1", "q2"])
        mock_client.batch_get_query_execution.assert_called_once_with(
            QueryExecutionIds=["q1", "q2"]
        )


class TestNamedQueries:
    def test_create_named_query(self, service, mock_client):
        mock_client.create_named_query.return_value = {"NamedQueryId": "nq-1"}
        service.create_named_query("my-query", "SELECT 1", "mydb")
        call_kwargs = mock_client.create_named_query.call_args[1]
        assert call_kwargs["Name"] == "my-query"
        assert call_kwargs["QueryString"] == "SELECT 1"
        assert call_kwargs["Database"] == "mydb"

    def test_create_named_query_with_all_params(self, service, mock_client):
        mock_client.create_named_query.return_value = {"NamedQueryId": "nq-1"}
        service.create_named_query("my-query", "SELECT 1", "mydb", description="desc", workgroup="wg1")
        call_kwargs = mock_client.create_named_query.call_args[1]
        assert call_kwargs["Description"] == "desc"
        assert call_kwargs["WorkGroup"] == "wg1"

    def test_list_named_queries(self, service, mock_client):
        mock_client.list_named_queries.return_value = {"NamedQueryIds": []}
        service.list_named_queries()
        mock_client.list_named_queries.assert_called_once_with()

    def test_list_named_queries_with_params(self, service, mock_client):
        mock_client.list_named_queries.return_value = {"NamedQueryIds": []}
        service.list_named_queries(workgroup="wg1", max_results=10, next_token="t")
        mock_client.list_named_queries.assert_called_once_with(
            WorkGroup="wg1", MaxResults=10, NextToken="t"
        )

    def test_get_named_query(self, service, mock_client):
        mock_client.get_named_query.return_value = {"NamedQuery": {}}
        service.get_named_query("nq-1")
        mock_client.get_named_query.assert_called_once_with(NamedQueryId="nq-1")

    def test_batch_get_named_query(self, service, mock_client):
        mock_client.batch_get_named_query.return_value = {"NamedQueries": []}
        service.batch_get_named_query(["nq-1", "nq-2"])
        mock_client.batch_get_named_query.assert_called_once_with(NamedQueryIds=["nq-1", "nq-2"])

    def test_delete_named_query(self, service, mock_client):
        mock_client.delete_named_query.return_value = {}
        service.delete_named_query("nq-1")
        mock_client.delete_named_query.assert_called_once_with(NamedQueryId="nq-1")


class TestPreparedStatements:
    def test_create_prepared_statement(self, service, mock_client):
        mock_client.create_prepared_statement.return_value = {}
        service.create_prepared_statement("stmt1", "wg1", "SELECT ?")
        call_kwargs = mock_client.create_prepared_statement.call_args[1]
        assert call_kwargs["StatementName"] == "stmt1"
        assert call_kwargs["WorkGroup"] == "wg1"
        assert call_kwargs["QueryStatement"] == "SELECT ?"

    def test_create_prepared_statement_with_description(self, service, mock_client):
        mock_client.create_prepared_statement.return_value = {}
        service.create_prepared_statement("stmt1", "wg1", "SELECT ?", description="my stmt")
        call_kwargs = mock_client.create_prepared_statement.call_args[1]
        assert call_kwargs["Description"] == "my stmt"

    def test_list_prepared_statements(self, service, mock_client):
        mock_client.list_prepared_statements.return_value = {"PreparedStatements": []}
        service.list_prepared_statements("wg1")
        mock_client.list_prepared_statements.assert_called_once_with(WorkGroup="wg1")

    def test_list_prepared_statements_with_params(self, service, mock_client):
        mock_client.list_prepared_statements.return_value = {"PreparedStatements": []}
        service.list_prepared_statements("wg1", max_results=5, next_token="t")
        mock_client.list_prepared_statements.assert_called_once_with(
            WorkGroup="wg1", MaxResults=5, NextToken="t"
        )

    def test_get_prepared_statement(self, service, mock_client):
        mock_client.get_prepared_statement.return_value = {"PreparedStatement": {}}
        service.get_prepared_statement("stmt1", "wg1")
        mock_client.get_prepared_statement.assert_called_once_with(
            StatementName="stmt1", WorkGroup="wg1"
        )

    def test_update_prepared_statement(self, service, mock_client):
        mock_client.update_prepared_statement.return_value = {}
        service.update_prepared_statement("stmt1", "wg1", "SELECT 2")
        call_kwargs = mock_client.update_prepared_statement.call_args[1]
        assert call_kwargs["QueryStatement"] == "SELECT 2"

    def test_update_prepared_statement_with_description(self, service, mock_client):
        mock_client.update_prepared_statement.return_value = {}
        service.update_prepared_statement("stmt1", "wg1", "SELECT 2", description="updated")
        assert mock_client.update_prepared_statement.call_args[1]["Description"] == "updated"

    def test_delete_prepared_statement(self, service, mock_client):
        mock_client.delete_prepared_statement.return_value = {}
        service.delete_prepared_statement("stmt1", "wg1")
        mock_client.delete_prepared_statement.assert_called_once_with(
            StatementName="stmt1", WorkGroup="wg1"
        )


class TestResolvers:
    def test_resolve_workgroup_no_schemas(self, mock_client):
        from argus.models.schemas import AppConfig
        svc = AthenaService(mock_client, AppConfig())
        assert svc._resolve_workgroup("mydb", None) is None

    def test_resolve_output_no_workgroup(self, service):
        result = service._resolve_output(None)
        assert result == "s3://results/default/"

    def test_resolve_output_workgroup_not_in_map(self, service):
        result = service._resolve_output("unknown-wg")
        assert result == "s3://results/default/"

    def test_resolve_output_workgroup_in_map(self, service):
        result = service._resolve_output("analytics_123456_prod")
        assert result == "s3://results/123456/prod/"
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
