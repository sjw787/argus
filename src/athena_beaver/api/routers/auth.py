from __future__ import annotations

import configparser
import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from athena_beaver.api.schemas import (
    AuthStatusResponse,
    ProfileSelectRequest,
    SsoAccount,
    SsoPollResponse,
    SsoRole,
    SsoSelectRoleRequest,
    SsoSelectRoleResponse,
    SsoStartRequest,
    SsoStartResponse,
)
from athena_beaver.api.dependencies import get_config
from athena_beaver.core.auth import reset_session_cache
from athena_beaver.models.schemas import AppConfig
from athena_beaver.services.sso_service import DeviceAuthSession, SsoService

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory store: session_id → DeviceAuthSession + optional access_token
_sessions: dict[str, DeviceAuthSession] = {}
_tokens: dict[str, str] = {}  # session_id → access_token


class SsoConfigResponse(BaseModel):
    start_url: Optional[str] = None
    region: Optional[str] = None
    profile: Optional[str] = None


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Optional[str] = None,
    region: Optional[str] = None,
):
    """Check whether valid AWS credentials are available."""
    resolved_profile = profile or config.aws.profile
    resolved_region = region or config.aws.region
    profiles = SsoService.list_profiles()
    authenticated = SsoService.check_credentials(profile=resolved_profile, region=resolved_region)
    return AuthStatusResponse(
        authenticated=authenticated,
        profile=resolved_profile,
        region=resolved_region,
        profiles=profiles,
    )


@router.get("/profiles", response_model=list[str])
def list_profiles():
    """Return all profile names from ~/.aws/credentials."""
    return SsoService.list_profiles()


@router.get("/sso-config", response_model=SsoConfigResponse)
def get_sso_config(config: Annotated[AppConfig, Depends(get_config)]):
    """Read the SSO start URL and region for the active profile from ~/.aws/config."""
    profile = config.aws.profile
    region = config.aws.region

    if not profile:
        return SsoConfigResponse(region=region)

    aws_config = Path.home() / ".aws" / "config"
    if not aws_config.exists():
        return SsoConfigResponse(profile=profile, region=region)

    cfg = configparser.ConfigParser()
    cfg.read(aws_config)

    section = profile if profile == "default" else f"profile {profile}"
    if section not in cfg:
        return SsoConfigResponse(profile=profile, region=region)

    s = cfg[section]
    start_url = s.get("sso_start_url") or s.get("sso_session")
    cfg_region = s.get("region") or region

    # If sso_start_url is a session name, look it up in the sso-session section
    if start_url and not start_url.startswith("http"):
        session_section = f"sso-session {start_url}"
        if session_section in cfg:
            start_url = cfg[session_section].get("sso_start_url", start_url)
            cfg_region = cfg[session_section].get("sso_region") or cfg_region

    return SsoConfigResponse(profile=profile, region=cfg_region, start_url=start_url)


@router.post("/profile/select", response_model=AuthStatusResponse)
def select_profile(body: ProfileSelectRequest, region: Optional[str] = None):
    """Switch the active profile (validates credentials exist)."""
    authenticated = SsoService.check_credentials(
        profile=body.profile_name, region=region
    )
    if not authenticated:
        raise HTTPException(
            status_code=400,
            detail=f"Profile '{body.profile_name}' has no valid credentials.",
        )
    reset_session_cache()
    profiles = SsoService.list_profiles()
    return AuthStatusResponse(
        authenticated=True,
        profile=body.profile_name,
        region=region,
        profiles=profiles,
    )


# ── SSO flow ──────────────────────────────────────────────────────────────────

@router.post("/sso/start", response_model=SsoStartResponse)
def sso_start(body: SsoStartRequest):
    """
    Begin SSO device-authorization flow.
    Returns a user_code and verification URL to open in the browser.
    """
    svc = SsoService(region=body.region)
    try:
        session = svc.start_login(start_url=body.start_url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session_id = str(uuid.uuid4())
    _sessions[session_id] = session

    return SsoStartResponse(
        session_id=session_id,
        user_code=session.user_code,
        verification_uri=session.verification_uri,
        verification_uri_complete=session.verification_uri_complete,
        expires_in=session.expires_in,
        interval=session.interval,
    )


@router.get("/sso/poll/{session_id}", response_model=SsoPollResponse)
def sso_poll(session_id: str):
    """
    Poll once to see if the user has completed browser authentication.
    Frontend calls this every `interval` seconds.
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session_id in _tokens:
        return SsoPollResponse(status="success", access_token=_tokens[session_id])

    svc = SsoService(region=session.region)
    try:
        token = svc.poll_token(session)
    except RuntimeError as exc:
        _sessions.pop(session_id, None)
        detail = str(exc)
        status = "expired" if "expired" in detail.lower() else "denied"
        return SsoPollResponse(status=status)

    if token:
        _tokens[session_id] = token
        return SsoPollResponse(status="success", access_token=token)

    return SsoPollResponse(status="pending")


@router.get("/sso/{session_id}/accounts", response_model=list[SsoAccount])
def sso_list_accounts(session_id: str):
    """List AWS accounts accessible with the SSO access token."""
    token = _tokens.get(session_id)
    if not token:
        raise HTTPException(status_code=400, detail="Not authenticated yet.")

    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    svc = SsoService(region=session.region)
    try:
        accounts = svc.list_accounts(token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [
        SsoAccount(account_id=a.account_id, account_name=a.account_name, email=a.email)
        for a in accounts
    ]


@router.get("/sso/{session_id}/accounts/{account_id}/roles", response_model=list[SsoRole])
def sso_list_roles(session_id: str, account_id: str):
    """List IAM roles available for a given account."""
    token = _tokens.get(session_id)
    if not token:
        raise HTTPException(status_code=400, detail="Not authenticated yet.")

    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    svc = SsoService(region=session.region)
    try:
        roles = svc.list_roles(token, account_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [SsoRole(account_id=r.account_id, role_name=r.role_name) for r in roles]


@router.post("/sso/select-role", response_model=SsoSelectRoleResponse)
def sso_select_role(body: SsoSelectRoleRequest):
    """
    Fetch role credentials and save them as a named profile in ~/.aws/credentials.
    """
    token = _tokens.get(body.session_id)
    if not token:
        raise HTTPException(status_code=400, detail="Not authenticated yet.")

    session = _sessions.get(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    svc = SsoService(region=session.region)
    try:
        creds = svc.get_credentials(token, body.account_id, body.role_name)
        svc.save_profile(
            profile_name=body.profile_name,
            credentials=creds,
            region=session.region,
            start_url=session.start_url,
            account_id=body.account_id,
            role_name=body.role_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Bust the boto3 session cache so subsequent requests use the new credentials
    reset_session_cache()

    # Clean up session memory
    _sessions.pop(body.session_id, None)
    _tokens.pop(body.session_id, None)

    return SsoSelectRoleResponse(
        profile_name=body.profile_name,
        expiration=creds.expiration,
        message=(
            f"Credentials saved as profile '{body.profile_name}'. "
            f"Expires: {creds.expiration}"
        ),
    )
