from __future__ import annotations

import configparser
import dataclasses
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from argus.api.schemas import (
    AuthStatusResponse,
    AuthConfigResponse,
    ProfileSelectRequest,
    SsoAccount,
    SsoPollResponse,
    SsoRole,
    SsoSelectRoleRequest,
    SsoSelectRoleResponse,
    SsoStartRequest,
    SsoStartResponse,
)
from argus.api.dependencies import get_config
from argus.core.auth import reset_session_cache
from argus.core.session_store import (
    delete_session,
    delete_token,
    get_session,
    get_token,
    put_session,
    put_token,
)
from argus.models.schemas import AppConfig
from argus.services.sso_service import DeviceAuthSession, SsoService

router = APIRouter(prefix="/auth", tags=["auth"])


class SsoConfigResponse(BaseModel):
    start_url: Optional[str] = None
    region: Optional[str] = None
    profile: Optional[str] = None


class AuthModeResponse(BaseModel):
    mode: str


# ── Auth mode ─────────────────────────────────────────────────────────────────

@router.get("/config", response_model=AuthConfigResponse)
def get_auth_config():
    """Return frontend auth / feature configuration (no credentials required)."""
    return AuthConfigResponse(
        mode=os.environ.get("ARGUS_AUTH_MODE", "sso"),
        streaming=os.environ.get("LAMBDA_RUNTIME", "") != "1",
        cognito_user_pool_id=os.environ.get("ARGUS_COGNITO_USER_POOL_ID") or None,
        cognito_client_id=os.environ.get("ARGUS_COGNITO_CLIENT_ID") or None,
        cognito_domain=os.environ.get("ARGUS_COGNITO_DOMAIN") or None,
    )


# ── Status ────────────────────────────────────────────────────────────────────


def _credentials_still_valid(creds_data: dict) -> bool:
    """Return True if stored SSO credentials have not yet expired."""
    expiration = creds_data.get("expiration")
    if not expiration:
        # No expiration stored — assume valid (caller decides)
        return True
    expiry_dt = None
    try:
        expiry_dt = datetime.fromisoformat(str(expiration).replace("Z", "+00:00"))
    except ValueError:
        try:
            # Legacy: Unix timestamp in milliseconds
            expiry_dt = datetime.fromtimestamp(int(expiration) / 1000, tz=timezone.utc)
        except (ValueError, TypeError):
            return False
    return datetime.now(timezone.utc) < expiry_dt


@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status(
    config: Annotated[AppConfig, Depends(get_config)],
    profile: Optional[str] = None,
    region: Optional[str] = None,
    x_credential_id: Optional[str] = Header(default=None),
):
    """Check whether valid AWS credentials are available.

    In Lambda/SSO mode the frontend sends X-Credential-Id on every request.
    We validate against the DynamoDB session store first so that a page refresh
    does not force a full re-login.
    """
    resolved_region = region or config.aws.region
    profiles = SsoService.list_profiles()

    # Fast path: credential stored in session store (Lambda SSO mode)
    if x_credential_id:
        creds_data = get_session(f"creds:{x_credential_id}")
        if creds_data and _credentials_still_valid(creds_data):
            resolved_profile = creds_data.get("profile") or profile or config.aws.profile
            return AuthStatusResponse(
                authenticated=True,
                profile=resolved_profile,
                region=resolved_region,
                profiles=profiles,
            )
        # Purge stale session so subsequent refreshes don't loop through 401s
        if creds_data and not _credentials_still_valid(creds_data):
            from argus.core.session_store import delete_session
            delete_session(f"creds:{x_credential_id}")

    # Fallback: check local AWS profile credentials (local dev mode)
    resolved_profile = profile or config.aws.profile
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
    """Read the SSO start URL and region for the active profile from ~/.aws/config.
    In Lambda mode, ARGUS_SSO_START_URL env var takes precedence.
    """
    region = config.aws.region

    # Lambda mode: return env-configured start URL directly
    env_start_url = os.environ.get("ARGUS_SSO_START_URL")
    if env_start_url:
        return SsoConfigResponse(start_url=env_start_url, region=region)

    profile = config.aws.profile
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
    put_session(session_id, dataclasses.asdict(session))

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
    session_data = get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found.")
    session = DeviceAuthSession(**session_data)

    token = get_token(session_id)
    if token:
        return SsoPollResponse(status="success", access_token=token)

    svc = SsoService(region=session.region)
    try:
        token = svc.poll_token(session)
    except RuntimeError as exc:
        delete_session(session_id)
        detail = str(exc)
        status = "expired" if "expired" in detail.lower() else "denied"
        return SsoPollResponse(status=status)

    if token:
        put_token(session_id, token)
        return SsoPollResponse(status="success", access_token=token)

    return SsoPollResponse(status="pending")


@router.get("/sso/{session_id}/accounts", response_model=list[SsoAccount])
def sso_list_accounts(session_id: str):
    """List AWS accounts accessible with the SSO access token."""
    token = get_token(session_id)
    if not token:
        raise HTTPException(status_code=400, detail="Not authenticated yet.")

    session_data = get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found.")
    session = DeviceAuthSession(**session_data)

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
    token = get_token(session_id)
    if not token:
        raise HTTPException(status_code=400, detail="Not authenticated yet.")

    session_data = get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found.")
    session = DeviceAuthSession(**session_data)

    svc = SsoService(region=session.region)
    try:
        roles = svc.list_roles(token, account_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return [SsoRole(account_id=r.account_id, role_name=r.role_name) for r in roles]


@router.post("/sso/select-role", response_model=SsoSelectRoleResponse)
def sso_select_role(body: SsoSelectRoleRequest):
    """
    Fetch role credentials.
    - Local dev: saves them as a named profile in ~/.aws/credentials.
    - Lambda (LAMBDA_RUNTIME=1): stores credentials in session_store and returns
      a credential_id the frontend should send as X-Credential-Id on future requests.
    """
    token = get_token(body.session_id)
    if not token:
        raise HTTPException(status_code=400, detail="Not authenticated yet.")

    session_data = get_session(body.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found.")
    session = DeviceAuthSession(**session_data)

    svc = SsoService(region=session.region)
    try:
        creds = svc.get_credentials(token, body.account_id, body.role_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    is_lambda = os.environ.get("LAMBDA_RUNTIME") == "1"

    if is_lambda:
        # Store credentials in session_store; return credential_id to the frontend.
        credential_id = body.session_id
        put_session(
            f"creds:{credential_id}",
            {
                "access_key_id": creds.access_key_id,
                "secret_access_key": creds.secret_access_key,
                "session_token": creds.session_token,
                "expiration": creds.expiration,
                "region": session.region,
            },
            ttl_seconds=28800,  # 8 hours — matches SSO credential lifetime
        )
        message = (
            f"Credentials stored for Lambda session '{body.profile_name}'. "
            f"Expires: {creds.expiration}"
        )
    else:
        try:
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
        credential_id = None
        message = (
            f"Credentials saved as profile '{body.profile_name}'. "
            f"Expires: {creds.expiration}"
        )

    # Clean up device-auth session data (credentials are stored separately)
    delete_session(body.session_id)
    delete_token(body.session_id)

    return SsoSelectRoleResponse(
        profile_name=body.profile_name,
        expiration=creds.expiration,
        credential_id=credential_id,
        message=message,
    )


@router.post("/logout")
def logout(x_credential_id: Annotated[Optional[str], Header()] = None):
    """
    Invalidate the current session.
    - Lambda mode: deletes the credential record from the session store.
    - Local mode: no server-side state to clear; client clears its own store.
    """
    if x_credential_id:
        delete_session(f"creds:{x_credential_id}")
    return {"ok": True}
