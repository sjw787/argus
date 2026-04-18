from __future__ import annotations
import pytest
from argus.models.schemas import AppConfig, AWSConfig, WorkgroupConfig, DefaultsConfig


@pytest.fixture
def sample_config():
    return AppConfig(
        aws=AWSConfig(region="us-east-1"),
        workgroups=WorkgroupConfig(
            output_locations={
                "analytics_123456_prod": "s3://results-prod/123456/",
                "analytics_123456789_dev": "s3://results-dev/123456789/",
            }
        ),
        defaults=DefaultsConfig(output_location="s3://results-default/"),
    )
