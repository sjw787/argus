"""AWS IAM Identity Center (SSO) device-authorization flow."""
from __future__ import annotations

import configparser
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import boto3


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DeviceAuthSession:
    """State returned from start_device_authorization."""
    client_id: str
    client_secret: str
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int
    start_url: str
    region: str
    started_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return time.time() > self.started_at + self.expires_in


@dataclass
class SsoAccount:
    account_id: str
    account_name: str
    email: str


@dataclass
class SsoRole:
    account_id: str
    role_name: str


@dataclass
class SsoCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str


# ── Service ───────────────────────────────────────────────────────────────────

class SsoService:
    """Orchestrates the SSO OIDC device-authorization login flow."""

    _CLIENT_NAME = "athena-beaver"
    _CLIENT_TYPE = "public"

    def __init__(self, region: str) -> None:
        self.region = region
        self._oidc = boto3.client("sso-oidc", region_name=region)
        self._sso = boto3.client("sso", region_name=region)

    # ── Step 1: register + start device auth ──────────────────────────────────

    def start_login(self, start_url: str) -> DeviceAuthSession:
        """Register client, start device-authorization flow, return session."""
        reg = self._oidc.register_client(
            clientName=self._CLIENT_NAME,
            clientType=self._CLIENT_TYPE,
        )
        client_id = reg["clientId"]
        client_secret = reg["clientSecret"]

        auth = self._oidc.start_device_authorization(
            clientId=client_id,
            clientSecret=client_secret,
            startUrl=start_url,
        )

        return DeviceAuthSession(
            client_id=client_id,
            client_secret=client_secret,
            device_code=auth["deviceCode"],
            user_code=auth["userCode"],
            verification_uri=auth["verificationUri"],
            verification_uri_complete=auth["verificationUriComplete"],
            expires_in=auth["expiresIn"],
            interval=auth["interval"],
            start_url=start_url,
            region=self.region,
        )

    # ── Step 2: poll for access token ─────────────────────────────────────────

    def poll_token(self, session: DeviceAuthSession) -> Optional[str]:
        """
        Attempt to exchange device code for access token.

        Returns the access token string on success, None if still pending.
        Raises RuntimeError on hard failure (expired, declined, etc.).
        """
        if session.is_expired():
            raise RuntimeError("Login session expired. Please start again.")

        try:
            resp = self._oidc.create_token(
                clientId=session.client_id,
                clientSecret=session.client_secret,
                grantType="urn:ietf:params:oauth:grant-type:device_code",
                deviceCode=session.device_code,
            )
            return resp["accessToken"]
        except self._oidc.exceptions.AuthorizationPendingException:
            return None
        except self._oidc.exceptions.SlowDownException:
            return None
        except self._oidc.exceptions.ExpiredTokenException as exc:
            raise RuntimeError("Login session expired. Please start again.") from exc
        except self._oidc.exceptions.AccessDeniedException as exc:
            raise RuntimeError("Login was denied by the user.") from exc

    # ── Step 3: list accounts ─────────────────────────────────────────────────

    def list_accounts(self, access_token: str) -> list[SsoAccount]:
        accounts: list[SsoAccount] = []
        paginator = self._sso.get_paginator("list_accounts")
        for page in paginator.paginate(accessToken=access_token):
            for a in page.get("accountList", []):
                accounts.append(SsoAccount(
                    account_id=a["accountId"],
                    account_name=a["accountName"],
                    email=a.get("emailAddress", ""),
                ))
        return accounts

    # ── Step 4: list roles for an account ─────────────────────────────────────

    def list_roles(self, access_token: str, account_id: str) -> list[SsoRole]:
        roles: list[SsoRole] = []
        paginator = self._sso.get_paginator("list_account_roles")
        for page in paginator.paginate(accessToken=access_token, accountId=account_id):
            for r in page.get("roleList", []):
                roles.append(SsoRole(
                    account_id=account_id,
                    role_name=r["roleName"],
                ))
        return roles

    # ── Step 5: get role credentials ──────────────────────────────────────────

    def get_credentials(
        self,
        access_token: str,
        account_id: str,
        role_name: str,
    ) -> SsoCredentials:
        resp = self._sso.get_role_credentials(
            accessToken=access_token,
            accountId=account_id,
            roleName=role_name,
        )
        creds = resp["roleCredentials"]
        return SsoCredentials(
            access_key_id=creds["accessKeyId"],
            secret_access_key=creds["secretAccessKey"],
            session_token=creds["sessionToken"],
            expiration=str(creds.get("expiration", "")),
        )

    # ── Step 6: persist to ~/.aws ─────────────────────────────────────────────

    @staticmethod
    def save_profile(
        profile_name: str,
        credentials: SsoCredentials,
        region: str,
        start_url: str,
        account_id: str,
        role_name: str,
    ) -> None:
        """Write credentials + config to ~/.aws/credentials and ~/.aws/config.

        When running on Lambda (LAMBDA_RUNTIME=1) file writes are skipped — the
        caller is responsible for storing credentials in the session_store.
        """
        import os as _os
        if _os.environ.get("LAMBDA_RUNTIME") == "1":
            return

        aws_dir = Path.home() / ".aws"
        aws_dir.mkdir(mode=0o700, exist_ok=True)

        # ── ~/.aws/credentials ────────────────────────────────────────────────
        creds_file = aws_dir / "credentials"
        creds_cfg = configparser.ConfigParser()
        if creds_file.exists():
            creds_cfg.read(creds_file)

        creds_cfg[profile_name] = {
            "aws_access_key_id": credentials.access_key_id,
            "aws_secret_access_key": credentials.secret_access_key,
            "aws_session_token": credentials.session_token,
        }
        with creds_file.open("w") as f:
            creds_cfg.write(f)
        creds_file.chmod(0o600)

        # ── ~/.aws/config ─────────────────────────────────────────────────────
        config_file = aws_dir / "config"
        config_cfg = configparser.ConfigParser()
        if config_file.exists():
            config_cfg.read(config_file)

        # boto3 reads profile sections as "profile <name>" (except "default")
        section = profile_name if profile_name == "default" else f"profile {profile_name}"
        # Only write region — NOT SSO fields. Static credentials in ~/.aws/credentials
        # take precedence and don't need token refresh. Writing sso_* fields here would
        # cause boto3 to use the SSO provider and require a cached token file.
        config_cfg[section] = {"region": region}
        with config_file.open("w") as f:
            config_cfg.write(f)
        config_file.chmod(0o600)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def list_profiles() -> list[str]:
        """Return profile names currently in ~/.aws/credentials."""
        creds_file = Path.home() / ".aws" / "credentials"
        if not creds_file.exists():
            return []
        cfg = configparser.ConfigParser()
        cfg.read(creds_file)
        return list(cfg.sections())

    @staticmethod
    def check_credentials(profile: Optional[str] = None, region: Optional[str] = None) -> bool:
        """Return True if boto3 can resolve credentials for the given profile."""
        # Fast path: check ~/.aws/credentials file directly first
        if profile:
            creds_file = Path.home() / ".aws" / "credentials"
            if creds_file.exists():
                cfg = configparser.ConfigParser()
                cfg.read(creds_file)
                if profile in cfg and cfg[profile].get("aws_access_key_id"):
                    return True

        # Full boto3 resolve (may trigger SSO provider chain — requires awscrt)
        try:
            session = boto3.Session(
                profile_name=profile,
                region_name=region,
            )
            creds = session.get_credentials()
            if creds is None:
                return False
            resolved = creds.resolve()
            return resolved is not None and resolved.access_key is not None
        except Exception:
            # MissingDependencyException (awscrt not installed), NoCredentialsError, etc.
            return False
