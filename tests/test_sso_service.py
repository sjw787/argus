"""Comprehensive tests for SsoService — AWS IAM Identity Center device-auth flow."""
from __future__ import annotations

import configparser
import time
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from argus.services.sso_service import (
    DeviceAuthSession,
    SsoCredentials,
    SsoService,
)


# ── Factories ─────────────────────────────────────────────────────────────────

def _make_service() -> tuple[SsoService, MagicMock, MagicMock]:
    """Return (SsoService, mock_oidc_client, mock_sso_client)."""
    with patch("boto3.client") as mock_boto_client:
        mock_oidc = MagicMock()
        mock_sso = MagicMock()
        mock_boto_client.side_effect = [mock_oidc, mock_sso]
        svc = SsoService(region="us-east-1")
    return svc, mock_oidc, mock_sso


def _device_session(**overrides) -> DeviceAuthSession:
    defaults = dict(
        client_id="cid",
        client_secret="csec",
        device_code="dcode",
        user_code="ABCD-1234",
        verification_uri="https://device.sso.example.com",
        verification_uri_complete="https://device.sso.example.com?code=ABCD-1234",
        expires_in=600,
        interval=5,
        start_url="https://start.awsapps.com/start",
        region="us-east-1",
        started_at=time.time(),
    )
    defaults.update(overrides)
    return DeviceAuthSession(**defaults)


def _make_creds(**overrides) -> SsoCredentials:
    defaults = dict(
        access_key_id="AKID",
        secret_access_key="secret",
        session_token="token",
        expiration="2099-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return SsoCredentials(**defaults)


# ── DeviceAuthSession.is_expired ───────────────────────────────────────────────

def test_device_auth_session_not_expired():
    session = _device_session(started_at=time.time(), expires_in=600)
    assert session.is_expired() is False


def test_device_auth_session_is_expired():
    session = _device_session(started_at=time.time() - 9999, expires_in=60)
    assert session.is_expired() is True


# ── start_login ───────────────────────────────────────────────────────────────

def test_start_login_returns_device_auth_session():
    svc, mock_oidc, _ = _make_service()
    mock_oidc.register_client.return_value = {"clientId": "cid", "clientSecret": "csec"}
    mock_oidc.start_device_authorization.return_value = {
        "deviceCode": "dcode",
        "userCode": "ABCD-1234",
        "verificationUri": "https://device.sso.example.com",
        "verificationUriComplete": "https://device.sso.example.com?code=ABCD-1234",
        "expiresIn": 600,
        "interval": 5,
    }

    session = svc.start_login("https://start.awsapps.com/start")

    assert isinstance(session, DeviceAuthSession)
    assert session.client_id == "cid"
    assert session.client_secret == "csec"
    assert session.device_code == "dcode"
    assert session.user_code == "ABCD-1234"
    assert session.start_url == "https://start.awsapps.com/start"
    assert session.region == "us-east-1"


def test_start_login_calls_register_client_with_correct_args():
    svc, mock_oidc, _ = _make_service()
    mock_oidc.register_client.return_value = {"clientId": "c", "clientSecret": "s"}
    mock_oidc.start_device_authorization.return_value = {
        "deviceCode": "d",
        "userCode": "U",
        "verificationUri": "v",
        "verificationUriComplete": "vc",
        "expiresIn": 100,
        "interval": 5,
    }

    svc.start_login("https://start.example.com")

    mock_oidc.register_client.assert_called_once_with(
        clientName="argus-for-athena",
        clientType="public",
    )


# ── poll_token ────────────────────────────────────────────────────────────────

def test_poll_token_returns_access_token_on_success():
    svc, mock_oidc, _ = _make_service()
    session = _device_session()
    mock_oidc.create_token.return_value = {"accessToken": "tok-123"}

    result = svc.poll_token(session)

    assert result == "tok-123"


def test_poll_token_returns_none_when_authorization_pending():
    svc, mock_oidc, _ = _make_service()
    session = _device_session()

    class AuthorizationPendingException(Exception):
        pass

    mock_oidc.exceptions.AuthorizationPendingException = AuthorizationPendingException
    mock_oidc.exceptions.SlowDownException = type("NeverRaised", (Exception,), {})
    mock_oidc.exceptions.ExpiredTokenException = type("NeverRaised2", (Exception,), {})
    mock_oidc.exceptions.AccessDeniedException = type("NeverRaised3", (Exception,), {})
    mock_oidc.create_token.side_effect = AuthorizationPendingException()

    assert svc.poll_token(session) is None


def test_poll_token_returns_none_when_slow_down():
    svc, mock_oidc, _ = _make_service()
    session = _device_session()

    class SlowDownException(Exception):
        pass

    mock_oidc.exceptions.AuthorizationPendingException = type("NeverRaised", (Exception,), {})
    mock_oidc.exceptions.SlowDownException = SlowDownException
    mock_oidc.exceptions.ExpiredTokenException = type("NeverRaised2", (Exception,), {})
    mock_oidc.exceptions.AccessDeniedException = type("NeverRaised3", (Exception,), {})
    mock_oidc.create_token.side_effect = SlowDownException()

    assert svc.poll_token(session) is None


def test_poll_token_raises_runtime_error_on_expired_token():
    svc, mock_oidc, _ = _make_service()
    session = _device_session()

    class ExpiredTokenException(Exception):
        pass

    mock_oidc.exceptions.AuthorizationPendingException = type("NeverRaised", (Exception,), {})
    mock_oidc.exceptions.SlowDownException = type("NeverRaised2", (Exception,), {})
    mock_oidc.exceptions.ExpiredTokenException = ExpiredTokenException
    mock_oidc.exceptions.AccessDeniedException = type("NeverRaised3", (Exception,), {})
    mock_oidc.create_token.side_effect = ExpiredTokenException()

    with pytest.raises(RuntimeError, match="expired"):
        svc.poll_token(session)


def test_poll_token_raises_runtime_error_on_access_denied():
    svc, mock_oidc, _ = _make_service()
    session = _device_session()

    class AccessDeniedException(Exception):
        pass

    mock_oidc.exceptions.AuthorizationPendingException = type("NeverRaised", (Exception,), {})
    mock_oidc.exceptions.SlowDownException = type("NeverRaised2", (Exception,), {})
    mock_oidc.exceptions.ExpiredTokenException = type("NeverRaised3", (Exception,), {})
    mock_oidc.exceptions.AccessDeniedException = AccessDeniedException
    mock_oidc.create_token.side_effect = AccessDeniedException()

    with pytest.raises(RuntimeError, match="denied"):
        svc.poll_token(session)


def test_poll_token_raises_when_session_already_expired():
    svc, mock_oidc, _ = _make_service()
    expired_session = _device_session(started_at=time.time() - 9999, expires_in=60)

    with pytest.raises(RuntimeError, match="expired"):
        svc.poll_token(expired_session)


# ── list_accounts ─────────────────────────────────────────────────────────────

def test_list_accounts_returns_all_accounts():
    svc, _, mock_sso = _make_service()
    paginator = MagicMock()
    mock_sso.get_paginator.return_value = paginator
    paginator.paginate.return_value = [
        {
            "accountList": [
                {
                    "accountId": "111111111111",
                    "accountName": "Prod",
                    "emailAddress": "prod@example.com",
                },
                {
                    "accountId": "222222222222",
                    "accountName": "Dev",
                    "emailAddress": "dev@example.com",
                },
            ]
        }
    ]

    accounts = svc.list_accounts("access-token")

    assert len(accounts) == 2
    assert accounts[0].account_id == "111111111111"
    assert accounts[0].account_name == "Prod"
    assert accounts[1].email == "dev@example.com"


def test_list_accounts_returns_empty_list_when_no_accounts():
    svc, _, mock_sso = _make_service()
    paginator = MagicMock()
    mock_sso.get_paginator.return_value = paginator
    paginator.paginate.return_value = [{"accountList": []}]

    assert svc.list_accounts("access-token") == []


def test_list_accounts_email_defaults_to_empty_when_missing():
    svc, _, mock_sso = _make_service()
    paginator = MagicMock()
    mock_sso.get_paginator.return_value = paginator
    paginator.paginate.return_value = [
        {"accountList": [{"accountId": "123", "accountName": "Acme"}]}
    ]

    accounts = svc.list_accounts("tok")
    assert accounts[0].email == ""


# ── list_roles ────────────────────────────────────────────────────────────────

def test_list_roles_returns_roles_for_account():
    svc, _, mock_sso = _make_service()
    paginator = MagicMock()
    mock_sso.get_paginator.return_value = paginator
    paginator.paginate.return_value = [
        {"roleList": [{"roleName": "ReadOnlyAccess"}, {"roleName": "AdminAccess"}]}
    ]

    roles = svc.list_roles("access-token", "111111111111")

    assert len(roles) == 2
    assert roles[0].role_name == "ReadOnlyAccess"
    assert roles[1].role_name == "AdminAccess"
    assert all(r.account_id == "111111111111" for r in roles)


def test_list_roles_empty():
    svc, _, mock_sso = _make_service()
    paginator = MagicMock()
    mock_sso.get_paginator.return_value = paginator
    paginator.paginate.return_value = [{"roleList": []}]

    assert svc.list_roles("tok", "123") == []


# ── get_credentials ───────────────────────────────────────────────────────────

def test_get_credentials_converts_millisecond_timestamp():
    svc, _, mock_sso = _make_service()
    # 1_700_000_000_000 ms → 2023-11-14
    mock_sso.get_role_credentials.return_value = {
        "roleCredentials": {
            "accessKeyId": "AKID",
            "secretAccessKey": "secret",
            "sessionToken": "token",
            "expiration": 1_700_000_000_000,
        }
    }

    creds = svc.get_credentials("tok", "123", "ReadOnly")

    assert creds.access_key_id == "AKID"
    assert creds.secret_access_key == "secret"
    assert creds.session_token == "token"
    assert "2023" in creds.expiration  # ISO 8601 format


def test_get_credentials_falls_back_to_raw_string_on_invalid_expiration():
    svc, _, mock_sso = _make_service()
    mock_sso.get_role_credentials.return_value = {
        "roleCredentials": {
            "accessKeyId": "AKID",
            "secretAccessKey": "sec",
            "sessionToken": "tok",
            "expiration": "not-a-timestamp",
        }
    }

    creds = svc.get_credentials("tok", "123", "ReadOnly")
    assert creds.expiration == "not-a-timestamp"


def test_get_credentials_empty_string_when_expiration_missing():
    svc, _, mock_sso = _make_service()
    mock_sso.get_role_credentials.return_value = {
        "roleCredentials": {
            "accessKeyId": "AKID",
            "secretAccessKey": "sec",
            "sessionToken": "tok",
        }
    }

    creds = svc.get_credentials("tok", "123", "ReadOnly")
    assert creds.expiration == ""


# ── save_profile ──────────────────────────────────────────────────────────────

def test_save_profile_skipped_in_lambda_mode():
    """When LAMBDA_RUNTIME=1, save_profile must return without writing any files."""
    creds = _make_creds()
    with patch.dict("os.environ", {"LAMBDA_RUNTIME": "1"}):
        with patch.object(Path, "home") as mock_home:
            SsoService.save_profile(
                "my-profile", creds, "us-east-1", "https://start", "123", "Role"
            )
            mock_home.assert_not_called()


def test_save_profile_writes_credentials_and_config_files(tmp_path):
    """save_profile creates ~/.aws/credentials and ~/.aws/config."""
    creds = _make_creds()
    with patch.dict("os.environ", {}, clear=False):
        # Ensure LAMBDA_RUNTIME is unset so the write path is taken
        import os as _os
        _os.environ.pop("LAMBDA_RUNTIME", None)
        with patch.object(Path, "home", return_value=tmp_path):
            SsoService.save_profile(
                "test-profile", creds, "us-east-1", "https://start", "123", "Role"
            )

    creds_cfg = configparser.ConfigParser()
    creds_cfg.read(tmp_path / ".aws" / "credentials")
    assert "test-profile" in creds_cfg
    assert creds_cfg["test-profile"]["aws_access_key_id"] == "AKID"
    assert creds_cfg["test-profile"]["aws_secret_access_key"] == "secret"
    assert creds_cfg["test-profile"]["aws_session_token"] == "token"

    config_cfg = configparser.ConfigParser()
    config_cfg.read(tmp_path / ".aws" / "config")
    assert "profile test-profile" in config_cfg
    assert config_cfg["profile test-profile"]["region"] == "us-east-1"


def test_save_profile_merges_existing_credentials_file(tmp_path):
    """save_profile must preserve existing profiles in ~/.aws/credentials."""
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir(mode=0o700)
    # Pre-populate with an existing profile
    existing_cfg = configparser.ConfigParser()
    existing_cfg["other-profile"] = {
        "aws_access_key_id": "OTHER",
        "aws_secret_access_key": "OTHER_SEC",
    }
    existing_cfg["profile other-config"] = {"region": "eu-west-1"}
    with (aws_dir / "credentials").open("w") as f:
        existing_cfg.write(f)
    with (aws_dir / "config").open("w") as f:
        existing_cfg.write(f)

    creds = _make_creds()
    import os as _os
    _os.environ.pop("LAMBDA_RUNTIME", None)
    with patch.object(Path, "home", return_value=tmp_path):
        SsoService.save_profile(
            "new-profile", creds, "us-west-2", "https://start", "456", "DevRole"
        )

    merged = configparser.ConfigParser()
    merged.read(tmp_path / ".aws" / "credentials")
    # Both profiles should be present
    assert "other-profile" in merged
    assert "new-profile" in merged
    assert merged["new-profile"]["aws_access_key_id"] == "AKID"


def test_save_profile_uses_default_section_for_default_profile(tmp_path):
    """The 'default' profile should NOT use the 'profile default' section."""
    creds = _make_creds()
    with patch.dict("os.environ", {}, clear=False):
        import os as _os
        _os.environ.pop("LAMBDA_RUNTIME", None)
        with patch.object(Path, "home", return_value=tmp_path):
            SsoService.save_profile(
                "default", creds, "us-west-2", "https://start", "123", "Role"
            )

    config_cfg = configparser.ConfigParser()
    config_cfg.read(tmp_path / ".aws" / "config")
    # boto3 convention: default profile uses bare "default" section
    assert "default" in config_cfg


# ── list_profiles ─────────────────────────────────────────────────────────────

def test_list_profiles_returns_all_profile_sections(tmp_path):
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    cfg = configparser.ConfigParser()
    cfg["default"] = {"aws_access_key_id": "k1", "aws_secret_access_key": "s1"}
    cfg["staging"] = {"aws_access_key_id": "k2", "aws_secret_access_key": "s2"}
    with (aws_dir / "credentials").open("w") as f:
        cfg.write(f)

    with patch.object(Path, "home", return_value=tmp_path):
        profiles = SsoService.list_profiles()

    assert "default" in profiles
    assert "staging" in profiles


def test_list_profiles_returns_empty_list_when_file_missing(tmp_path):
    with patch.object(Path, "home", return_value=tmp_path):
        assert SsoService.list_profiles() == []


# ── check_credentials ─────────────────────────────────────────────────────────

def test_check_credentials_true_when_key_found_in_credentials_file(tmp_path):
    aws_dir = tmp_path / ".aws"
    aws_dir.mkdir()
    cfg = configparser.ConfigParser()
    cfg["dev"] = {"aws_access_key_id": "AKID", "aws_secret_access_key": "sec"}
    with (aws_dir / "credentials").open("w") as f:
        cfg.write(f)

    with patch.object(Path, "home", return_value=tmp_path):
        assert SsoService.check_credentials(profile="dev") is True


def test_check_credentials_false_when_boto3_returns_none_credentials(tmp_path):
    """Falls through to boto3 when no profile is supplied."""
    with patch.object(Path, "home", return_value=tmp_path):
        with patch("boto3.Session") as MockSession:
            mock_sess = MagicMock()
            MockSession.return_value = mock_sess
            mock_sess.get_credentials.return_value = None

            assert SsoService.check_credentials() is False


def test_check_credentials_false_when_resolved_access_key_is_none(tmp_path):
    with patch.object(Path, "home", return_value=tmp_path):
        with patch("boto3.Session") as MockSession:
            mock_sess = MagicMock()
            MockSession.return_value = mock_sess
            resolved = MagicMock()
            resolved.access_key = None
            mock_sess.get_credentials.return_value.resolve.return_value = resolved

            assert SsoService.check_credentials() is False


def test_check_credentials_false_on_exception(tmp_path):
    with patch.object(Path, "home", return_value=tmp_path):
        with patch("boto3.Session", side_effect=Exception("NoCredentialsError")):
            assert SsoService.check_credentials(profile="bad-profile") is False
