from __future__ import annotations
from pathlib import Path
from typing import Optional, Annotated
from fastapi import Depends, Query
from athena_beaver.core.config import load_config
from athena_beaver.core.auth import get_athena_client, get_glue_client, get_s3_client
from athena_beaver.models.schemas import AppConfig
from athena_beaver.services.athena_service import AthenaService
from athena_beaver.services.catalog_service import CatalogService
from athena_beaver.services.workgroup_service import WorkgroupService

_config_path: Optional[Path] = None


def set_config_path(path: Optional[Path]) -> None:
    global _config_path
    _config_path = path


def get_config() -> AppConfig:
    return load_config(_config_path)


def get_athena_service(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Annotated[Optional[str], Query()] = None,
    region: Annotated[Optional[str], Query()] = None,
) -> AthenaService:
    cfg_profile = profile or config.aws.profile
    cfg_region = region or config.aws.region
    client = get_athena_client(cfg_profile, cfg_region)
    return AthenaService(client, config)


def get_catalog_service(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Annotated[Optional[str], Query()] = None,
    region: Annotated[Optional[str], Query()] = None,
) -> CatalogService:
    cfg_profile = profile or config.aws.profile
    cfg_region = region or config.aws.region
    client = get_glue_client(cfg_profile, cfg_region)
    return CatalogService(client, config)


def get_workgroup_service(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Annotated[Optional[str], Query()] = None,
    region: Annotated[Optional[str], Query()] = None,
) -> WorkgroupService:
    cfg_profile = profile or config.aws.profile
    cfg_region = region or config.aws.region
    client = get_athena_client(cfg_profile, cfg_region)
    return WorkgroupService(client, config)


def get_s3(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Annotated[Optional[str], Query()] = None,
    region: Annotated[Optional[str], Query()] = None,
):
    cfg_profile = profile or config.aws.profile
    cfg_region = region or config.aws.region
    return get_s3_client(cfg_profile, cfg_region)
