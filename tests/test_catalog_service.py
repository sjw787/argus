from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from athena_beaver.services.catalog_service import CatalogService
from athena_beaver.models.schemas import AppConfig, NamingSchema


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


def test_list_tables(service, mock_client):
    mock_client.get_tables.return_value = {"TableList": []}
    service.list_tables("mydb")
    mock_client.get_tables.assert_called_once_with(DatabaseName="mydb")
