from __future__ import annotations
import time
from typing import Optional
import boto3


_session_cache: dict[tuple, tuple[boto3.Session, float]] = {}
_SESSION_TTL = 3600  # 1 hour — boto3 Sessions using IAM/profile credentials


def get_session_from_credentials(
    access_key_id: str,
    secret_access_key: str,
    session_token: Optional[str] = None,
    region: Optional[str] = None,
) -> boto3.Session:
    """Create a boto3 Session from explicit credentials (used in Lambda SSO mode)."""
    return boto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=session_token or None,
        region_name=region,
    )


def get_session(
    profile: Optional[str] = None,
    region: Optional[str] = None,
) -> boto3.Session:
    key = (profile, region)
    entry = _session_cache.get(key)
    if entry and time.monotonic() - entry[1] < _SESSION_TTL:
        return entry[0]
    kwargs: dict = {}
    if profile:
        kwargs["profile_name"] = profile
    if region:
        kwargs["region_name"] = region
    session = boto3.Session(**kwargs)
    _session_cache[key] = (session, time.monotonic())
    return session


def invalidate_session(
    profile: Optional[str] = None,
    region: Optional[str] = None,
) -> None:
    """Remove a specific cache entry, e.g. after an ExpiredToken error."""
    _session_cache.pop((profile, region), None)


def reset_session_cache() -> None:
    _session_cache.clear()


def get_athena_client(
    profile: Optional[str] = None,
    region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
):
    return get_session(profile, region).client("athena", endpoint_url=endpoint_url)


def get_glue_client(
    profile: Optional[str] = None,
    region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
):
    return get_session(profile, region).client("glue", endpoint_url=endpoint_url)


def get_s3_client(
    profile: Optional[str] = None,
    region: Optional[str] = None,
    endpoint_url: Optional[str] = None,
):
    return get_session(profile, region).client("s3", endpoint_url=endpoint_url)
