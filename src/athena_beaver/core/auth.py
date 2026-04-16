from __future__ import annotations
from typing import Optional
import boto3


_session_cache: dict[tuple, boto3.Session] = {}


def get_session(
    profile: Optional[str] = None,
    region: Optional[str] = None,
) -> boto3.Session:
    key = (profile, region)
    if key not in _session_cache:
        kwargs: dict = {}
        if profile:
            kwargs["profile_name"] = profile
        if region:
            kwargs["region_name"] = region
        _session_cache[key] = boto3.Session(**kwargs)
    return _session_cache[key]


def reset_session_cache() -> None:
    _session_cache.clear()


def get_athena_client(
    profile: Optional[str] = None,
    region: Optional[str] = None,
):
    return get_session(profile, region).client("athena")


def get_glue_client(
    profile: Optional[str] = None,
    region: Optional[str] = None,
):
    return get_session(profile, region).client("glue")


def get_s3_client(
    profile: Optional[str] = None,
    region: Optional[str] = None,
):
    return get_session(profile, region).client("s3")
