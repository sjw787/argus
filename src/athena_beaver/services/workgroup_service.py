from __future__ import annotations
from typing import Optional, Any
from athena_beaver.models.schemas import AppConfig


class WorkgroupService:
    def __init__(self, client, config: AppConfig):
        self._client = client
        self._config = config

    def list_work_groups(
        self,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {}
        if max_results:
            params["MaxResults"] = max_results
        if next_token:
            params["NextToken"] = next_token
        return self._client.list_work_groups(**params)

    def get_work_group(self, work_group: str) -> dict:
        return self._client.get_work_group(WorkGroup=work_group)

    def create_work_group(
        self,
        name: str,
        description: Optional[str] = None,
        configuration: Optional[dict] = None,
        tags: Optional[dict[str, str]] = None,
    ) -> dict:
        params: dict[str, Any] = {"Name": name}
        if description:
            params["Description"] = description
        if configuration:
            params["Configuration"] = configuration
        if tags:
            params["Tags"] = [{"Key": k, "Value": v} for k, v in tags.items()]
        return self._client.create_work_group(**params)

    def update_work_group(
        self,
        work_group: str,
        description: Optional[str] = None,
        configuration_updates: Optional[dict] = None,
        state: Optional[str] = None,
    ) -> dict:
        params: dict[str, Any] = {"WorkGroup": work_group}
        if description:
            params["Description"] = description
        if configuration_updates:
            params["ConfigurationUpdates"] = configuration_updates
        if state:
            params["State"] = state
        return self._client.update_work_group(**params)

    def delete_work_group(
        self,
        work_group: str,
        recursive_delete_option: bool = False,
    ) -> dict:
        return self._client.delete_work_group(
            WorkGroup=work_group,
            RecursiveDeleteOption=recursive_delete_option,
        )

    def list_tags_for_resource(self, resource_arn: str) -> dict:
        return self._client.list_tags_for_resource(ResourceARN=resource_arn)

    def tag_resource(self, resource_arn: str, tags: dict[str, str]) -> dict:
        return self._client.tag_resource(
            ResourceARN=resource_arn,
            Tags=[{"Key": k, "Value": v} for k, v in tags.items()],
        )

    def untag_resource(self, resource_arn: str, tag_keys: list[str]) -> dict:
        return self._client.untag_resource(ResourceARN=resource_arn, TagKeys=tag_keys)
