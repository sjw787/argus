from __future__ import annotations
import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Annotated, Optional

import boto3
from fastapi import Depends, Header, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from athena_beaver.core.config import load_config
from athena_beaver.core.auth import (
    get_athena_client,
    get_glue_client,
    get_s3_client,
    get_session_from_credentials,
)
from athena_beaver.core.session_store import get_session as get_stored_session
from athena_beaver.models.schemas import AppConfig
from athena_beaver.services.athena_service import AthenaService
from athena_beaver.services.catalog_service import CatalogService
from athena_beaver.services.workgroup_service import WorkgroupService

logger = logging.getLogger(__name__)

_config_path: Optional[Path] = None
_http_bearer = HTTPBearer(auto_error=False)


def set_config_path(path: Optional[Path]) -> None:
    global _config_path
    _config_path = path


def get_config() -> AppConfig:
    return load_config(_config_path)


# ── Cognito JWT validation ────────────────────────────────────────────────────

def _validate_cognito_token(token: str) -> dict:
    """Validate a Cognito JWT; return user payload dict or raise HTTP 401."""
    try:
        import jwt
        from jwt import PyJWKClient, PyJWTError
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="PyJWT not installed.") from exc

    region = os.environ.get("AB_REGION", "us-east-1")
    user_pool_id = os.environ.get("AB_COGNITO_USER_POOL_ID", "")
    client_id = os.environ.get("AB_COGNITO_CLIENT_ID", "")

    if not user_pool_id or not client_id:
        raise HTTPException(status_code=500, detail="Cognito env vars not configured.")

    jwks_url = (
        f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        "/.well-known/jwks.json"
    )

    try:
        jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=86400)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            options={"verify_exp": True},
        )
    except Exception as exc:  # PyJWTError, urllib errors, etc.
        logger.debug("Cognito JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    email = (
        payload.get("email")
        or payload.get("cognito:username")
        or payload.get("sub", "unknown")
    )
    return {"user": email, "auth_mode": "cognito"}


# ── Current user dependency ───────────────────────────────────────────────────

def get_current_user(
    request: Request,
    bearer: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_http_bearer)] = None,
    x_credential_id: Annotated[Optional[str], Header()] = None,
) -> dict:
    """Return current user identity. Behaviour is controlled by AB_AUTH_MODE."""
    auth_mode = os.environ.get("AB_AUTH_MODE", "sso")

    if auth_mode == "none":
        return {"user": "system", "auth_mode": "none"}

    if auth_mode == "cognito":
        if not bearer:
            raise HTTPException(status_code=401, detail="Authorization header required.")
        return _validate_cognito_token(bearer.credentials)

    # SSO mode — on Lambda, validate the stored credential_id
    if os.environ.get("LAMBDA_RUNTIME") == "1":
        if not x_credential_id:
            raise HTTPException(status_code=401, detail="X-Credential-Id header required.")
        creds_data = get_stored_session(f"creds:{x_credential_id}")
        if not creds_data:
            raise HTTPException(status_code=401, detail="Session not found or expired.")
        return {"user": x_credential_id, "auth_mode": "sso"}

    return {"user": "authenticated", "auth_mode": "sso"}


# ── boto3 session from stored credentials (Lambda SSO) ────────────────────────

def _boto3_session_from_credential_id(
    credential_id: Optional[str],
    region: Optional[str],
) -> Optional[boto3.Session]:
    """Build a boto3 Session from session_store credentials, or return None."""
    if not credential_id:
        return None
    creds_data = get_stored_session(f"creds:{credential_id}")
    if not creds_data:
        return None
    return get_session_from_credentials(
        access_key_id=creds_data["access_key_id"],
        secret_access_key=creds_data["secret_access_key"],
        session_token=creds_data.get("session_token"),
        region=region or creds_data.get("region"),
    )


# ── Service factories ─────────────────────────────────────────────────────────

def get_athena_service(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Annotated[Optional[str], Query()] = None,
    region: Annotated[Optional[str], Query()] = None,
    x_credential_id: Annotated[Optional[str], Header()] = None,
) -> AthenaService:
    cfg_profile = profile or config.aws.profile
    cfg_region = region or config.aws.region
    session = _boto3_session_from_credential_id(x_credential_id, cfg_region)
    client = session.client("athena") if session else get_athena_client(cfg_profile, cfg_region)
    return AthenaService(client, config)


def get_catalog_service(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Annotated[Optional[str], Query()] = None,
    region: Annotated[Optional[str], Query()] = None,
    x_credential_id: Annotated[Optional[str], Header()] = None,
) -> CatalogService:
    cfg_profile = profile or config.aws.profile
    cfg_region = region or config.aws.region
    session = _boto3_session_from_credential_id(x_credential_id, cfg_region)
    client = session.client("glue") if session else get_glue_client(cfg_profile, cfg_region)
    return CatalogService(client, config)


def get_workgroup_service(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Annotated[Optional[str], Query()] = None,
    region: Annotated[Optional[str], Query()] = None,
    x_credential_id: Annotated[Optional[str], Header()] = None,
) -> WorkgroupService:
    cfg_profile = profile or config.aws.profile
    cfg_region = region or config.aws.region
    session = _boto3_session_from_credential_id(x_credential_id, cfg_region)
    client = session.client("athena") if session else get_athena_client(cfg_profile, cfg_region)
    return WorkgroupService(client, config)


def get_s3(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Annotated[Optional[str], Query()] = None,
    region: Annotated[Optional[str], Query()] = None,
    x_credential_id: Annotated[Optional[str], Header()] = None,
):
    cfg_profile = profile or config.aws.profile
    cfg_region = region or config.aws.region
    session = _boto3_session_from_credential_id(x_credential_id, cfg_region)
    if session:
        return session.client("s3")
    return get_s3_client(cfg_profile, cfg_region)
