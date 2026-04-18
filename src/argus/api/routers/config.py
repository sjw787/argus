from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from argus.api.schemas import ConfigInfo
from argus.api.dependencies import get_config
from argus.api.routers.catalog import _db_cache
from argus.models.schemas import AppConfig
from argus.core.config import save_config

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigInfo)
def get_config_info(config: Annotated[AppConfig, Depends(get_config)]):
    return ConfigInfo(
        region=config.aws.region,
        profile=config.aws.profile,
        workgroup_output_locations=config.workgroups.output_locations,
        default_output_location=config.defaults.output_location,
        max_results=config.defaults.max_results,
        query_timeout_seconds=config.defaults.query_timeout_seconds,
        locked_settings=config.locked_settings,
    )


class DatabaseAssignmentRequest(BaseModel):
    database: str
    workgroup: str


class DatabaseAssignmentsResponse(BaseModel):
    assignments: dict[str, str]


@router.get("/assignments", response_model=DatabaseAssignmentsResponse)
def get_assignments(config: Annotated[AppConfig, Depends(get_config)]):
    return DatabaseAssignmentsResponse(assignments=config.workgroups.assignments)


@router.post("/assignments", response_model=DatabaseAssignmentsResponse)
def assign_database(body: DatabaseAssignmentRequest, config: Annotated[AppConfig, Depends(get_config)]):
    updated_assignments = {**config.workgroups.assignments, body.database: body.workgroup}
    updated_workgroups = config.workgroups.model_copy(update={"assignments": updated_assignments})
    updated_config = config.model_copy(update={"workgroups": updated_workgroups})
    save_config(updated_config)
    _db_cache.invalidate_all()
    return DatabaseAssignmentsResponse(assignments=updated_assignments)


@router.delete("/assignments/{database}", response_model=DatabaseAssignmentsResponse)
def unassign_database(database: str, config: Annotated[AppConfig, Depends(get_config)]):
    updated_assignments = {k: v for k, v in config.workgroups.assignments.items() if k != database}
    updated_workgroups = config.workgroups.model_copy(update={"assignments": updated_assignments})
    updated_config = config.model_copy(update={"workgroups": updated_workgroups})
    save_config(updated_config)
    _db_cache.invalidate_all()
    return DatabaseAssignmentsResponse(assignments=updated_assignments)

