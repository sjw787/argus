"""Tests for the in-memory and DynamoDB session store backends."""
from __future__ import annotations

import json
import time
import pytest
from unittest.mock import patch


def _clear_store():
    import argus.core.session_store as ss
    ss._memory_store.clear()


@pytest.fixture(autouse=True)
def clean_memory_store():
    _clear_store()
    yield
    _clear_store()


@pytest.fixture(autouse=True)
def force_memory_backend(clean_memory_store):
    with patch.dict("os.environ", {"ARGUS_SESSION_STORE": "memory"}):
        yield


# --- put / get ---

def test_put_and_get_session():
    from argus.core.session_store import put_session, get_session
    put_session("s1", {"user": "alice"})
    assert get_session("s1") == {"user": "alice"}


def test_get_missing_session_returns_none():
    from argus.core.session_store import get_session
    assert get_session("nonexistent") is None


def test_get_expired_session_returns_none():
    from argus.core.session_store import put_session, get_session
    put_session("s-exp", {"x": 1}, ttl_seconds=1)
    with patch("argus.core.session_store.time") as mock_time:
        mock_time.time.return_value = time.time() + 9999
        assert get_session("s-exp") is None


def test_expired_session_is_removed_from_store():
    import argus.core.session_store as ss
    from argus.core.session_store import put_session, get_session
    put_session("s-del", {"x": 1}, ttl_seconds=1)
    with patch("argus.core.session_store.time") as mock_time:
        mock_time.time.return_value = time.time() + 9999
        get_session("s-del")
    assert "s-del" not in ss._memory_store


# --- delete ---

def test_delete_session():
    from argus.core.session_store import put_session, get_session, delete_session
    put_session("s2", {"y": 2})
    delete_session("s2")
    assert get_session("s2") is None


def test_delete_nonexistent_session_is_noop():
    from argus.core.session_store import delete_session
    delete_session("ghost")  # should not raise


# --- token helpers ---

def test_put_and_get_token():
    from argus.core.session_store import put_token, get_token
    put_token("user-1", "tok-abc")
    assert get_token("user-1") == "tok-abc"


def test_get_token_missing_returns_none():
    from argus.core.session_store import get_token
    assert get_token("nobody") is None


def test_delete_token():
    from argus.core.session_store import put_token, get_token, delete_token
    put_token("user-2", "tok-xyz")
    delete_token("user-2")
    assert get_token("user-2") is None


# --- persistent helpers ---

def test_put_and_get_persistent():
    from argus.core.session_store import put_persistent, get_persistent
    put_persistent("cfg:overrides", {"theme": "dark"})
    assert get_persistent("cfg:overrides") == {"theme": "dark"}


def test_get_persistent_missing_returns_none():
    from argus.core.session_store import get_persistent
    assert get_persistent("cfg:nonexistent") is None


def test_put_persistent_overwrites():
    from argus.core.session_store import put_persistent, get_persistent
    put_persistent("cfg:key", {"v": 1})
    put_persistent("cfg:key", {"v": 2})
    assert get_persistent("cfg:key") == {"v": 2}


def test_persistent_entry_has_long_ttl():
    import argus.core.session_store as ss
    import time as real_time
    from argus.core.session_store import put_persistent
    put_persistent("cfg:ttl", {"x": 1})
    entry = ss._memory_store["cfg:ttl"]
    # Should expire ~10 years from now — at minimum 1 year
    assert entry["expires_at"] > real_time.time() + 365 * 24 * 3600

def test_overwrite_session():
    from argus.core.session_store import put_session, get_session
    put_session("s3", {"v": 1})
    put_session("s3", {"v": 2})
    assert get_session("s3") == {"v": 2}


# =============================================================================
# DynamoDB backend tests
# =============================================================================
# These tests override the module-level force_memory_backend autouse fixture by
# setting ARGUS_SESSION_STORE=dynamodb via monkeypatch inside each test, and
# use moto to provide a fake DynamoDB table.

try:
    from moto import mock_aws as _mock_aws
    _MOTO_AVAILABLE = True
except ImportError:
    _MOTO_AVAILABLE = False


def _create_dynamo_table():
    import boto3
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    table = ddb.create_table(
        TableName="argus-sessions",
        KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "session_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


@pytest.fixture
def dynamo_env(monkeypatch):
    """Switch the session store to DynamoDB and activate moto mocking."""
    monkeypatch.setenv("ARGUS_SESSION_STORE", "dynamodb")
    monkeypatch.setenv("ARGUS_SESSION_TABLE", "argus-sessions")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_put_and_get_session(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import put_session, get_session

        put_session("ddb-s1", {"user": "alice"})
        result = get_session("ddb-s1")

    assert result == {"user": "alice"}


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_get_missing_session_returns_none(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import get_session

        assert get_session("ghost") is None


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_get_expired_session_returns_none(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import put_session, get_session

        put_session("ddb-exp", {"x": 1}, ttl_seconds=60)

        with patch("argus.core.session_store.time") as mock_time:
            mock_time.time.return_value = time.time() + 9999
            result = get_session("ddb-exp")

    assert result is None


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_delete_session(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import put_session, get_session, delete_session

        put_session("ddb-del", {"y": 2})
        delete_session("ddb-del")
        assert get_session("ddb-del") is None


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_delete_nonexistent_session_is_noop(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import delete_session

        delete_session("nonexistent")  # must not raise


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_put_and_get_persistent(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import put_persistent, get_persistent

        put_persistent("cfg:overrides", {"theme": "dark"})
        result = get_persistent("cfg:overrides")

    assert result == {"theme": "dark"}


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_get_persistent_missing_returns_none(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import get_persistent

        assert get_persistent("cfg:missing") is None


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_put_persistent_overwrites(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import put_persistent, get_persistent

        put_persistent("cfg:key", {"v": 1})
        put_persistent("cfg:key", {"v": 2})
        assert get_persistent("cfg:key") == {"v": 2}


@pytest.mark.skipif(not _MOTO_AVAILABLE, reason="moto not installed")
def test_dynamodb_token_helpers(dynamo_env):
    from moto import mock_aws

    with mock_aws():
        _create_dynamo_table()
        from argus.core.session_store import put_token, get_token, delete_token

        put_token("user-ddb", "tok-xyz")
        assert get_token("user-ddb") == "tok-xyz"

        delete_token("user-ddb")
        assert get_token("user-ddb") is None
