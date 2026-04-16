from __future__ import annotations
import pytest
from athena_beaver.models.schemas import AppConfig, NamingSchema, AWSConfig, WorkgroupConfig, DefaultsConfig


@pytest.fixture
def sample_config():
    return AppConfig(
        aws=AWSConfig(region="us-east-1"),
        naming_schemas={
            "default": NamingSchema(
                pattern="{purpose}_{client_id}_{environment}",
                client_id_regex=r"\d{6}|\d{9}",
                workgroup_pattern="{purpose}_{client_id}_{environment}",
            ),
            "short": NamingSchema(
                pattern="{client_id}_{purpose}",
                client_id_regex=r"[a-z]{3}\d{4}",
                workgroup_pattern="wg_{client_id}",
            ),
        },
        active_schema="default",
        workgroups=WorkgroupConfig(
            output_locations={
                "analytics_123456_prod": "s3://results-prod/123456/",
                "analytics_123456789_dev": "s3://results-dev/123456789/",
            }
        ),
        defaults=DefaultsConfig(output_location="s3://results-default/"),
    )
