from __future__ import annotations
import re
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from botocore.exceptions import ClientError

from argus.api.schemas import (
    WorkgroupItem, WorkgroupCreate, WorkgroupUpdate, TagItem,
)
from argus.api.dependencies import get_workgroup_service, get_config, get_s3
from argus.services.workgroup_service import WorkgroupService
from argus.models.schemas import AppConfig
from argus.api.errors import sanitize_error

router = APIRouter(prefix="/workgroups", tags=["workgroups"])


class S3ValidateRequest(BaseModel):
    location: str


class S3ValidateResponse(BaseModel):
    valid: bool
    bucket: Optional[str] = None
    prefix: Optional[str] = None
    error: Optional[str] = None


def _parse_s3_url(location: str) -> tuple[str, str]:
    """Return (bucket, prefix) from an s3:// URL. Raises ValueError on bad format."""
    m = re.match(r"^s3://([^/]+)(/.*)?$", location.strip().rstrip("/") + "/")
    if not m:
        raise ValueError("Location must start with s3:// followed by a bucket name")
    bucket = m.group(1)
    prefix = (m.group(2) or "/").lstrip("/")
    return bucket, prefix


@router.post("/validate-s3", response_model=S3ValidateResponse)
def validate_s3_location(
    body: S3ValidateRequest,
    s3=Depends(get_s3),
):
    """Check that an S3 location exists and is writable with the current credentials."""
    try:
        bucket, prefix = _parse_s3_url(body.location)
    except ValueError as exc:
        return S3ValidateResponse(valid=False, error=str(exc))

    # 1. Check bucket exists and we can access it
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("403", "AccessDenied"):
            return S3ValidateResponse(
                valid=False, bucket=bucket,
                error=f"Bucket '{bucket}' exists but access is denied",
            )
        if code in ("404", "NoSuchBucket"):
            return S3ValidateResponse(
                valid=False, bucket=bucket,
                error=f"Bucket '{bucket}' does not exist",
            )
        return S3ValidateResponse(valid=False, bucket=bucket, error=str(e))

    # 2. Verify write permission by attempting a zero-byte put then deleting it
    probe_key = f"{prefix}_argus_write_check"
    try:
        s3.put_object(Bucket=bucket, Key=probe_key, Body=b"")
        s3.delete_object(Bucket=bucket, Key=probe_key)
    except ClientError as e:
        return S3ValidateResponse(
            valid=False, bucket=bucket, prefix=prefix,
            error=f"Bucket is readable but write access was denied: {e.response['Error']['Message']}",
        )

    return S3ValidateResponse(valid=True, bucket=bucket, prefix=prefix)




@router.get("/names", response_model=list[str])
def list_workgroup_names(
    svc: Annotated[WorkgroupService, Depends(get_workgroup_service)],
):
    """Return all workgroup names in the account, paginating through all results."""
    names = []
    next_token = None
    while True:
        resp = svc.list_work_groups(max_results=50, next_token=next_token)
        for wg in resp.get("WorkGroups", []):
            names.append(wg["Name"])
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return sorted(name for name in names if name != "primary")


def _parse_wg(wg: dict) -> WorkgroupItem:
    cfg = wg.get("Configuration", {})
    rc = cfg.get("ResultConfiguration", {})
    ev = cfg.get("EngineVersion", {})
    return WorkgroupItem(
        name=wg["Name"],
        state=wg.get("State"),
        description=wg.get("Description"),
        output_location=rc.get("OutputLocation"),
        engine_version=ev.get("SelectedEngineVersion"),
        created_time=str(wg.get("CreationTime", "")) or None,
    )


@router.get("", response_model=list[WorkgroupItem])
def list_workgroups(
    svc: Annotated[WorkgroupService, Depends(get_workgroup_service)],
    max_results: int = Query(default=50),
):
    try:
        resp = svc.list_work_groups(max_results=max_results)
        result = []
        for wg_summary in resp.get("WorkGroups", []):
            try:
                detail = svc.get_work_group(wg_summary["Name"])
                result.append(_parse_wg(detail["WorkGroup"]))
            except Exception:
                result.append(WorkgroupItem(name=wg_summary["Name"], state=wg_summary.get("State")))
        return result
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Workgroup operation failed")


@router.get("/{name}", response_model=WorkgroupItem)
def get_workgroup(
    name: str,
    svc: Annotated[WorkgroupService, Depends(get_workgroup_service)],
):
    try:
        resp = svc.get_work_group(name)
        return _parse_wg(resp["WorkGroup"])
    except Exception as e:
        raise sanitize_error(e, status_code=404, public_message="Workgroup operation failed")


@router.post("", response_model=WorkgroupItem)
def create_workgroup(
    body: WorkgroupCreate,
    svc: Annotated[WorkgroupService, Depends(get_workgroup_service)],
):
    config = {}
    if body.output_location:
        config["ResultConfiguration"] = {"OutputLocation": body.output_location}
    if body.engine_version:
        config["EngineVersion"] = {"SelectedEngineVersion": body.engine_version}
    try:
        svc.create_work_group(body.name, body.description, configuration=config or None, tags=body.tags or None)
        return WorkgroupItem(name=body.name, description=body.description, output_location=body.output_location)
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Workgroup operation failed")


@router.put("/{name}", response_model=WorkgroupItem)
def update_workgroup(
    name: str,
    body: WorkgroupUpdate,
    svc: Annotated[WorkgroupService, Depends(get_workgroup_service)],
):
    config_updates = {}
    if body.output_location:
        config_updates["ResultConfigurationUpdates"] = {"OutputLocation": body.output_location}
    try:
        svc.update_work_group(name, description=body.description, configuration_updates=config_updates or None, state=body.state)
        resp = svc.get_work_group(name)
        return _parse_wg(resp["WorkGroup"])
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Workgroup operation failed")


@router.delete("/{name}")
def delete_workgroup(
    name: str,
    svc: Annotated[WorkgroupService, Depends(get_workgroup_service)],
    recursive: bool = Query(default=False),
):
    try:
        svc.delete_work_group(name, recursive_delete_option=recursive)
        return {"message": f"Workgroup {name} deleted"}
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Workgroup operation failed")


@router.get("/{name}/tags", response_model=list[TagItem])
def list_tags(
    name: str,
    svc: Annotated[WorkgroupService, Depends(get_workgroup_service)],
    resource_arn: str = Query(...),
):
    try:
        resp = svc.list_tags_for_resource(resource_arn)
        return [TagItem(key=t["Key"], value=t["Value"]) for t in resp.get("Tags", [])]
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Workgroup operation failed")


@router.put("/{name}/tags")
def update_tags(
    name: str,
    tags: list[TagItem],
    svc: Annotated[WorkgroupService, Depends(get_workgroup_service)],
    resource_arn: str = Query(...),
):
    try:
        tag_dict = {t.key: t.value for t in tags}
        svc.tag_resource(resource_arn, tag_dict)
        return {"message": "Tags updated"}
    except Exception as e:
        raise sanitize_error(e, status_code=400, public_message="Workgroup operation failed")
