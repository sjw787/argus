from __future__ import annotations
import time
from typing import Optional, Any
from argus.models.schemas import AppConfig
from argus.core.naming import get_resolver


class AthenaService:
    def __init__(self, client, config: AppConfig):
        self._client = client
        self._config = config

    def start_query_execution(
        self,
        query: str,
        database: str,
        workgroup: Optional[str] = None,
        output_location: Optional[str] = None,
        schema_name: Optional[str] = None,
    ) -> dict:
        """Start a query. Auto-resolves workgroup from database name if not provided."""
        resolved_wg = workgroup or self._resolve_workgroup(database, schema_name)
        resolved_s3 = output_location or self._resolve_output(resolved_wg)

        params: dict[str, Any] = {
            "QueryString": query,
            "QueryExecutionContext": {"Database": database},
        }
        if resolved_wg:
            params["WorkGroup"] = resolved_wg
        if resolved_s3:
            params["ResultConfiguration"] = {"OutputLocation": resolved_s3}

        return self._client.start_query_execution(**params)

    def get_query_execution(self, query_execution_id: str) -> dict:
        return self._client.get_query_execution(QueryExecutionId=query_execution_id)

    def stop_query_execution(self, query_execution_id: str) -> dict:
        return self._client.stop_query_execution(QueryExecutionId=query_execution_id)

    def get_query_results(
        self,
        query_execution_id: str,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {"QueryExecutionId": query_execution_id}
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        return self._client.get_query_results(**params)

    def list_query_executions(
        self,
        workgroup: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {}
        if workgroup:
            params["WorkGroup"] = workgroup
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        return self._client.list_query_executions(**params)

    def batch_get_query_execution(self, query_execution_ids: list[str]) -> dict:
        return self._client.batch_get_query_execution(QueryExecutionIds=query_execution_ids)

    def wait_for_query(
        self,
        query_execution_id: str,
        poll_interval: float = 1.0,
        timeout: Optional[float] = None,
    ) -> dict:
        """Poll until query completes. Returns final execution details."""
        start = time.monotonic()
        while True:
            resp = self.get_query_execution(query_execution_id)
            state = resp["QueryExecution"]["Status"]["State"]
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                return resp
            if timeout and (time.monotonic() - start) > timeout:
                raise TimeoutError(f"Query {query_execution_id} timed out after {timeout}s")
            time.sleep(poll_interval)

    def create_named_query(
        self,
        name: str,
        query: str,
        database: str,
        description: Optional[str] = None,
        workgroup: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "Name": name,
            "QueryString": query,
            "Database": database,
        }
        if description:
            params["Description"] = description
        if workgroup:
            params["WorkGroup"] = workgroup
        return self._client.create_named_query(**params)

    def list_named_queries(
        self,
        workgroup: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {}
        if workgroup:
            params["WorkGroup"] = workgroup
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        return self._client.list_named_queries(**params)

    def get_named_query(self, named_query_id: str) -> dict:
        return self._client.get_named_query(NamedQueryId=named_query_id)

    def batch_get_named_query(self, named_query_ids: list[str]) -> dict:
        return self._client.batch_get_named_query(NamedQueryIds=named_query_ids)

    def delete_named_query(self, named_query_id: str) -> dict:
        return self._client.delete_named_query(NamedQueryId=named_query_id)

    def create_prepared_statement(
        self,
        statement_name: str,
        workgroup: str,
        query: str,
        description: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "StatementName": statement_name,
            "WorkGroup": workgroup,
            "QueryStatement": query,
        }
        if description:
            params["Description"] = description
        return self._client.create_prepared_statement(**params)

    def list_prepared_statements(
        self,
        workgroup: str,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {"WorkGroup": workgroup}
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        return self._client.list_prepared_statements(**params)

    def get_prepared_statement(self, statement_name: str, workgroup: str) -> dict:
        return self._client.get_prepared_statement(
            StatementName=statement_name, WorkGroup=workgroup
        )

    def update_prepared_statement(
        self,
        statement_name: str,
        workgroup: str,
        query: str,
        description: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "StatementName": statement_name,
            "WorkGroup": workgroup,
            "QueryStatement": query,
        }
        if description:
            params["Description"] = description
        return self._client.update_prepared_statement(**params)

    def delete_prepared_statement(self, statement_name: str, workgroup: str) -> dict:
        return self._client.delete_prepared_statement(
            StatementName=statement_name, WorkGroup=workgroup
        )

    def _resolve_workgroup(self, database: str, schema_name: Optional[str]) -> Optional[str]:
        resolver = get_resolver(self._config, schema_name)
        if resolver is None:
            return None
        return resolver.resolve_workgroup(database)

    def _resolve_output(self, workgroup: Optional[str]) -> Optional[str]:
        if workgroup and workgroup in self._config.workgroups.output_locations:
            return self._config.workgroups.output_locations[workgroup]
        return self._config.defaults.output_location
