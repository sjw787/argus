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


def test_tag_resource(service):
    service._client.tag_resource.return_value = {}
    service.tag_resource("arn:aws:...", {"env": "prod", "team": "data"})
    call_kwargs = service._client.tag_resource.call_args[1]
    tags = {t["Key"]: t["Value"] for t in call_kwargs["Tags"]}
    assert tags == {"env": "prod", "team": "data"}
