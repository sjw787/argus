from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from argus.services.workgroup_service import WorkgroupService
from argus.models.schemas import AppConfig


@pytest.fixture
def service():
    return WorkgroupService(MagicMock(), AppConfig())


def test_list_work_groups(service):
    service._client.list_work_groups.return_value = {"WorkGroups": []}
    service.list_work_groups()
    service._client.list_work_groups.assert_called_once_with()


def test_get_work_group(service):
    service._client.get_work_group.return_value = {"WorkGroup": {"Name": "my-wg"}}
    service.get_work_group("my-wg")
    service._client.get_work_group.assert_called_once_with(WorkGroup="my-wg")


def test_create_work_group(service):
    service._client.create_work_group.return_value = {}
    service.create_work_group("new-wg", description="test")
    service._client.create_work_group.assert_called_once()
    assert service._client.create_work_group.call_args[1]["Name"] == "new-wg"


def test_delete_work_group(service):
    service._client.delete_work_group.return_value = {}
    service.delete_work_group("my-wg")
    service._client.delete_work_group.assert_called_once_with(
        WorkGroup="my-wg", RecursiveDeleteOption=False
    )


def test_list_work_groups_with_params(service):
    service._client.list_work_groups.return_value = {"WorkGroups": []}
    service.list_work_groups(max_results=10, next_token="tok")
    service._client.list_work_groups.assert_called_once_with(MaxResults=10, NextToken="tok")


def test_create_work_group_with_config_and_tags(service):
    service._client.create_work_group.return_value = {}
    service.create_work_group(
        "wg1",
        configuration={"ResultConfiguration": {"OutputLocation": "s3://out/"}},
        tags={"env": "prod"},
    )
    call_kwargs = service._client.create_work_group.call_args[1]
    assert "Configuration" in call_kwargs
    tags = {t["Key"]: t["Value"] for t in call_kwargs["Tags"]}
    assert tags == {"env": "prod"}


def test_update_work_group(service):
    service._client.update_work_group.return_value = {}
    service.update_work_group("wg1", description="updated", state="DISABLED")
    call_kwargs = service._client.update_work_group.call_args[1]
    assert call_kwargs["Description"] == "updated"
    assert call_kwargs["State"] == "DISABLED"


def test_update_work_group_with_config(service):
    service._client.update_work_group.return_value = {}
    service.update_work_group("wg1", configuration_updates={"EnforceWorkGroupConfiguration": True})
    call_kwargs = service._client.update_work_group.call_args[1]
    assert "ConfigurationUpdates" in call_kwargs


def test_delete_work_group_recursive(service):
    service._client.delete_work_group.return_value = {}
    service.delete_work_group("wg1", recursive_delete_option=True)
    service._client.delete_work_group.assert_called_once_with(
        WorkGroup="wg1", RecursiveDeleteOption=True
    )


def test_list_tags_for_resource(service):
    service._client.list_tags_for_resource.return_value = {"Tags": []}
    service.list_tags_for_resource("arn:aws:athena:us-east-1:123:workgroup/wg1")
    service._client.list_tags_for_resource.assert_called_once_with(
        ResourceARN="arn:aws:athena:us-east-1:123:workgroup/wg1"
    )


def test_untag_resource(service):
    service._client.untag_resource.return_value = {}
    service.untag_resource("arn:aws:...", ["env", "team"])
    service._client.untag_resource.assert_called_once_with(
        ResourceARN="arn:aws:...", TagKeys=["env", "team"]
    )
    service._client.tag_resource.return_value = {}
    service.tag_resource("arn:aws:...", {"env": "prod", "team": "data"})
    call_kwargs = service._client.tag_resource.call_args[1]
    tags = {t["Key"]: t["Value"] for t in call_kwargs["Tags"]}
    assert tags == {"env": "prod", "team": "data"}
