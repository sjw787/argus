from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from argus.services.catalog_service import CatalogService
from argus.models.schemas import AppConfig, NamingSchema


@pytest.fixture
def config():
    return AppConfig(
        naming_schemas={
            "default": NamingSchema(
                pattern="{purpose}_{client_id}_{environment}",
                client_id_regex=r"\d{6}|\d{9}",
                workgroup_pattern="{purpose}_{client_id}_{environment}",
            )
        },
        active_schema="default",
    )


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def service(mock_client, config):
    return CatalogService(mock_client, config)


def test_list_databases_calls_get_databases(service, mock_client):
    mock_client.get_databases.return_value = {"DatabaseList": []}
    service.list_databases()
    mock_client.get_databases.assert_called_once()


def test_get_database(service, mock_client):
    mock_client.get_database.return_value = {"Database": {"Name": "mydb"}}
    resp = service.get_database("mydb")
    mock_client.get_database.assert_called_once_with(Name="mydb")


def test_create_database(service, mock_client):
    mock_client.create_database.return_value = {}
    service.create_database("newdb", description="test db")
    mock_client.create_database.assert_called_once()
    call_kwargs = mock_client.create_database.call_args[1]
    assert call_kwargs["DatabaseInput"]["Name"] == "newdb"
    assert call_kwargs["DatabaseInput"]["Description"] == "test db"


def test_search_databases_by_client_id(service, mock_client):
    mock_client.get_databases.return_value = {
        "DatabaseList": [
            {"Name": "analytics_123456_prod"},
            {"Name": "analytics_999999_prod"},
            {"Name": "reporting_123456_dev"},
        ]
    }
    results = service.search_databases_by_client_id("123456")
    names = [db["Name"] for db in results]
    assert "analytics_123456_prod" in names
    assert "reporting_123456_dev" in names
    assert "analytics_999999_prod" not in names


def test_list_databases_with_optional_params(service, mock_client):
    mock_client.get_databases.return_value = {"DatabaseList": []}
    service.list_databases(catalog_id="123", max_results=10, next_token="tok", resource_share_type="ALL")
    mock_client.get_databases.assert_called_once_with(
        CatalogId="123", MaxResults=10, NextToken="tok", ResourceShareType="ALL"
    )


def test_get_database_with_catalog_id(service, mock_client):
    mock_client.get_database.return_value = {"Database": {"Name": "mydb"}}
    service.get_database("mydb", catalog_id="cat123")
    mock_client.get_database.assert_called_once_with(Name="mydb", CatalogId="cat123")


def test_create_database_with_all_params(service, mock_client):
    mock_client.create_database.return_value = {}
    service.create_database(
        "newdb",
        description="desc",
        location_uri="s3://bucket/",
        parameters={"k": "v"},
        catalog_id="cat1",
    )
    call_kwargs = mock_client.create_database.call_args[1]
    db_input = call_kwargs["DatabaseInput"]
    assert db_input["Description"] == "desc"
    assert db_input["LocationUri"] == "s3://bucket/"
    assert db_input["Parameters"] == {"k": "v"}
    assert call_kwargs["CatalogId"] == "cat1"


def test_delete_database(service, mock_client):
    mock_client.delete_database.return_value = {}
    service.delete_database("olddb")
    mock_client.delete_database.assert_called_once_with(Name="olddb")


def test_delete_database_with_catalog_id(service, mock_client):
    mock_client.delete_database.return_value = {}
    service.delete_database("olddb", catalog_id="cat1")
    mock_client.delete_database.assert_called_once_with(Name="olddb", CatalogId="cat1")


def test_search_databases_by_client_id_pagination(service, mock_client):
    mock_client.get_databases.side_effect = [
        {"DatabaseList": [{"Name": "analytics_123456_prod"}], "NextToken": "t1"},
        {"DatabaseList": [{"Name": "reporting_123456_dev"}]},
    ]
    results = service.search_databases_by_client_id("123456")
    assert len(results) == 2
    assert mock_client.get_databases.call_count == 2


def test_search_databases_by_client_id_no_resolver(mock_client):
    from argus.models.schemas import AppConfig
    svc = CatalogService(mock_client, AppConfig())
    mock_client.get_databases.return_value = {
        "DatabaseList": [{"Name": "client123_data"}, {"Name": "other_db"}]
    }
    results = svc.search_databases_by_client_id("client123")
    names = [d["Name"] for d in results]
    assert "client123_data" in names
    assert "other_db" not in names


def test_list_tables(service, mock_client):
    mock_client.get_tables.return_value = {"TableList": []}
    service.list_tables("mydb")
    mock_client.get_tables.assert_called_once_with(DatabaseName="mydb")


def test_list_tables_with_optional_params(service, mock_client):
    mock_client.get_tables.return_value = {"TableList": []}
    service.list_tables("mydb", catalog_id="c1", expression="test*", max_results=5, next_token="t")
    mock_client.get_tables.assert_called_once_with(
        DatabaseName="mydb", CatalogId="c1", Expression="test*", MaxResults=5, NextToken="t"
    )


def test_get_table(service, mock_client):
    mock_client.get_table.return_value = {"Table": {"Name": "orders"}}
    service.get_table("mydb", "orders")
    mock_client.get_table.assert_called_once_with(DatabaseName="mydb", Name="orders")


def test_get_table_with_catalog_id(service, mock_client):
    mock_client.get_table.return_value = {"Table": {"Name": "orders"}}
    service.get_table("mydb", "orders", catalog_id="c1")
    mock_client.get_table.assert_called_once_with(DatabaseName="mydb", Name="orders", CatalogId="c1")


def test_create_table(service, mock_client):
    mock_client.create_table.return_value = {}
    service.create_table("mydb", {"Name": "t1", "StorageDescriptor": {}})
    mock_client.create_table.assert_called_once()
    assert mock_client.create_table.call_args[1]["DatabaseName"] == "mydb"


def test_create_table_with_partition_indexes(service, mock_client):
    mock_client.create_table.return_value = {}
    service.create_table("mydb", {"Name": "t1"}, catalog_id="c1", partition_indexes=[{"Keys": ["dt"]}])
    call_kwargs = mock_client.create_table.call_args[1]
    assert call_kwargs["CatalogId"] == "c1"
    assert call_kwargs["PartitionIndexes"] == [{"Keys": ["dt"]}]


def test_update_table(service, mock_client):
    mock_client.update_table.return_value = {}
    service.update_table("mydb", {"Name": "t1"})
    mock_client.update_table.assert_called_once()
    assert mock_client.update_table.call_args[1]["DatabaseName"] == "mydb"


def test_update_table_with_all_params(service, mock_client):
    mock_client.update_table.return_value = {}
    service.update_table("mydb", {"Name": "t1"}, catalog_id="c1", version_id="v2", skip_archive=True)
    call_kwargs = mock_client.update_table.call_args[1]
    assert call_kwargs["CatalogId"] == "c1"
    assert call_kwargs["VersionId"] == "v2"
    assert call_kwargs["SkipArchive"] is True


def test_delete_table(service, mock_client):
    mock_client.delete_table.return_value = {}
    service.delete_table("mydb", "orders")
    mock_client.delete_table.assert_called_once_with(DatabaseName="mydb", Name="orders")


def test_delete_table_with_catalog_id(service, mock_client):
    mock_client.delete_table.return_value = {}
    service.delete_table("mydb", "orders", catalog_id="c1")
    mock_client.delete_table.assert_called_once_with(DatabaseName="mydb", Name="orders", CatalogId="c1")


def test_batch_delete_table(service, mock_client):
    mock_client.batch_delete_table.return_value = {"Errors": []}
    service.batch_delete_table("mydb", ["t1", "t2"])
    mock_client.batch_delete_table.assert_called_once_with(
        DatabaseName="mydb", TablesToDelete=["t1", "t2"]
    )


def test_batch_delete_table_with_catalog_id(service, mock_client):
    mock_client.batch_delete_table.return_value = {"Errors": []}
    service.batch_delete_table("mydb", ["t1"], catalog_id="c1")
    assert mock_client.batch_delete_table.call_args[1]["CatalogId"] == "c1"


def test_get_table_versions(service, mock_client):
    mock_client.get_table_versions.return_value = {"TableVersions": []}
    service.get_table_versions("mydb", "orders")
    mock_client.get_table_versions.assert_called_once()
    call_kwargs = mock_client.get_table_versions.call_args[1]
    assert call_kwargs["DatabaseName"] == "mydb"
    assert call_kwargs["TableName"] == "orders"


def test_get_table_versions_with_params(service, mock_client):
    mock_client.get_table_versions.return_value = {"TableVersions": []}
    service.get_table_versions("mydb", "orders", catalog_id="c1", max_results=3, next_token="t")
    call_kwargs = mock_client.get_table_versions.call_args[1]
    assert call_kwargs["CatalogId"] == "c1"
    assert call_kwargs["MaxResults"] == 3
    assert call_kwargs["NextToken"] == "t"


def test_get_partitions(service, mock_client):
    mock_client.get_partitions.return_value = {"Partitions": []}
    service.get_partitions("mydb", "orders")
    call_kwargs = mock_client.get_partitions.call_args[1]
    assert call_kwargs["DatabaseName"] == "mydb"
    assert call_kwargs["TableName"] == "orders"


def test_get_partitions_with_all_params(service, mock_client):
    mock_client.get_partitions.return_value = {"Partitions": []}
    service.get_partitions("mydb", "orders", catalog_id="c1", expression="dt='2024'", max_results=50, next_token="t")
    call_kwargs = mock_client.get_partitions.call_args[1]
    assert call_kwargs["CatalogId"] == "c1"
    assert call_kwargs["Expression"] == "dt='2024'"
    assert call_kwargs["MaxResults"] == 50


def test_batch_get_partition(service, mock_client):
    mock_client.batch_get_partition.return_value = {"Partitions": []}
    service.batch_get_partition("mydb", "orders", [{"Values": ["2024"]}])
    call_kwargs = mock_client.batch_get_partition.call_args[1]
    assert call_kwargs["DatabaseName"] == "mydb"
    assert call_kwargs["PartitionsToGet"] == [{"Values": ["2024"]}]


def test_batch_get_partition_with_catalog_id(service, mock_client):
    mock_client.batch_get_partition.return_value = {"Partitions": []}
    service.batch_get_partition("mydb", "orders", [], catalog_id="c1")
    assert mock_client.batch_get_partition.call_args[1]["CatalogId"] == "c1"


def test_create_partition(service, mock_client):
    mock_client.create_partition.return_value = {}
    service.create_partition("mydb", "orders", {"Values": ["2024"]})
    call_kwargs = mock_client.create_partition.call_args[1]
    assert call_kwargs["DatabaseName"] == "mydb"
    assert call_kwargs["TableName"] == "orders"
    assert call_kwargs["PartitionInput"] == {"Values": ["2024"]}


def test_create_partition_with_catalog_id(service, mock_client):
    mock_client.create_partition.return_value = {}
    service.create_partition("mydb", "orders", {"Values": ["2024"]}, catalog_id="c1")
    assert mock_client.create_partition.call_args[1]["CatalogId"] == "c1"


def test_delete_partition(service, mock_client):
    mock_client.delete_partition.return_value = {}
    service.delete_partition("mydb", "orders", ["2024"])
    call_kwargs = mock_client.delete_partition.call_args[1]
    assert call_kwargs["DatabaseName"] == "mydb"
    assert call_kwargs["PartitionValues"] == ["2024"]


def test_delete_partition_with_catalog_id(service, mock_client):
    mock_client.delete_partition.return_value = {}
    service.delete_partition("mydb", "orders", ["2024"], catalog_id="c1")
    assert mock_client.delete_partition.call_args[1]["CatalogId"] == "c1"
