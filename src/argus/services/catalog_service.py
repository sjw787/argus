from __future__ import annotations
from typing import Optional, Any
from argus.models.schemas import AppConfig
from argus.core.naming import get_resolver


class CatalogService:
    def __init__(self, client, config: AppConfig):
        self._client = client
        self._config = config

    def list_databases(
        self,
        catalog_id: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        resource_share_type: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {}
        if catalog_id:
            params["CatalogId"] = catalog_id
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        if resource_share_type:
            params["ResourceShareType"] = resource_share_type
        return self._client.get_databases(**params)

    def get_database(self, name: str, catalog_id: Optional[str] = None) -> dict:
        params: dict[str, Any] = {"Name": name}
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.get_database(**params)

    def create_database(
        self,
        name: str,
        description: Optional[str] = None,
        location_uri: Optional[str] = None,
        parameters: Optional[dict[str, str]] = None,
        catalog_id: Optional[str] = None,
    ) -> dict:
        db_input: dict[str, Any] = {"Name": name}
        if description:
            db_input["Description"] = description
        if location_uri:
            db_input["LocationUri"] = location_uri
        if parameters:
            db_input["Parameters"] = parameters

        params: dict[str, Any] = {"DatabaseInput": db_input}
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.create_database(**params)

    def delete_database(self, name: str, catalog_id: Optional[str] = None) -> dict:
        params: dict[str, Any] = {"Name": name}
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.delete_database(**params)

    def search_databases_by_client_id(
        self,
        client_id: str,
        schema_name: Optional[str] = None,
        catalog_id: Optional[str] = None,
    ) -> list[dict]:
        """Return all databases whose name contains the given client_id according to the active schema."""
        resolver = get_resolver(self._config, schema_name)
        all_dbs: list[dict] = []
        next_token = None
        while True:
            resp = self.list_databases(catalog_id=catalog_id, next_token=next_token)
            for db in resp.get("DatabaseList", []):
                db_name = db["Name"]
                extracted = resolver.get_client_id(db_name) if resolver else None
                if extracted == client_id or client_id in db_name:
                    all_dbs.append(db)
            next_token = resp.get("NextToken")
            if not next_token:
                break
        return all_dbs

    def list_tables(
        self,
        database_name: str,
        catalog_id: Optional[str] = None,
        expression: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {"DatabaseName": database_name}
        if catalog_id:
            params["CatalogId"] = catalog_id
        if expression:
            params["Expression"] = expression
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        return self._client.get_tables(**params)

    def get_table(
        self, database_name: str, table_name: str, catalog_id: Optional[str] = None
    ) -> dict:
        params: dict[str, Any] = {"DatabaseName": database_name, "Name": table_name}
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.get_table(**params)

    def create_table(
        self,
        database_name: str,
        table_input: dict,
        catalog_id: Optional[str] = None,
        partition_indexes: Optional[list] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "DatabaseName": database_name,
            "TableInput": table_input,
        }
        if catalog_id:
            params["CatalogId"] = catalog_id
        if partition_indexes:
            params["PartitionIndexes"] = partition_indexes
        return self._client.create_table(**params)

    def update_table(
        self,
        database_name: str,
        table_input: dict,
        catalog_id: Optional[str] = None,
        version_id: Optional[str] = None,
        skip_archive: Optional[bool] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "DatabaseName": database_name,
            "TableInput": table_input,
        }
        if catalog_id:
            params["CatalogId"] = catalog_id
        if version_id:
            params["VersionId"] = version_id
        if skip_archive is not None:
            params["SkipArchive"] = skip_archive
        return self._client.update_table(**params)

    def delete_table(
        self,
        database_name: str,
        table_name: str,
        catalog_id: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {"DatabaseName": database_name, "Name": table_name}
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.delete_table(**params)

    def batch_delete_table(
        self,
        database_name: str,
        tables_to_delete: list[str],
        catalog_id: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "DatabaseName": database_name,
            "TablesToDelete": tables_to_delete,
        }
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.batch_delete_table(**params)

    def get_table_versions(
        self,
        database_name: str,
        table_name: str,
        catalog_id: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {"DatabaseName": database_name, "TableName": table_name}
        if catalog_id:
            params["CatalogId"] = catalog_id
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        return self._client.get_table_versions(**params)

    def get_partitions(
        self,
        database_name: str,
        table_name: str,
        catalog_id: Optional[str] = None,
        expression: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "DatabaseName": database_name,
            "TableName": table_name,
        }
        if catalog_id:
            params["CatalogId"] = catalog_id
        if expression:
            params["Expression"] = expression
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        return self._client.get_partitions(**params)

    def batch_get_partition(
        self,
        database_name: str,
        table_name: str,
        partitions_to_get: list[dict],
        catalog_id: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "DatabaseName": database_name,
            "TableName": table_name,
            "PartitionsToGet": partitions_to_get,
        }
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.batch_get_partition(**params)

    def create_partition(
        self,
        database_name: str,
        table_name: str,
        partition_input: dict,
        catalog_id: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "DatabaseName": database_name,
            "TableName": table_name,
            "PartitionInput": partition_input,
        }
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.create_partition(**params)

    def delete_partition(
        self,
        database_name: str,
        table_name: str,
        partition_values: list[str],
        catalog_id: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {
            "DatabaseName": database_name,
            "TableName": table_name,
            "PartitionValues": partition_values,
        }
        if catalog_id:
            params["CatalogId"] = catalog_id
        return self._client.delete_partition(**params)
