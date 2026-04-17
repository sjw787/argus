"""
Session store with DynamoDB backend for Lambda and in-memory fallback for local dev.
Controlled by ARGUS_SESSION_STORE env var: 'dynamodb' | 'memory' (default: 'memory')
DynamoDB table: argus-sessions, PK=session_id, TTL on expires_at field.
"""
from __future__ import annotations

import os
import time
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# In-memory fallback store: key → {"data": ..., "expires_at": float}
_memory_store: dict[str, dict] = {}


def _use_dynamodb() -> bool:
    return os.environ.get("ARGUS_SESSION_STORE", "memory") == "dynamodb"


def _get_table():
    import boto3
    table_name = os.environ.get("ARGUS_SESSION_TABLE", "argus-sessions")
    ddb = boto3.resource("dynamodb")
    return ddb.Table(table_name)


def put_session(session_id: str, data: dict[str, Any], ttl_seconds: int = 600) -> None:
    expires_at = int(time.time()) + ttl_seconds
    if _use_dynamodb():
        table = _get_table()
        table.put_item(Item={
            "session_id": session_id,
            "data": json.dumps(data),
            "expires_at": expires_at,
        })
        logger.debug("DynamoDB put_session: %s", session_id)
    else:
        _memory_store[session_id] = {"data": data, "expires_at": expires_at}


def put_persistent(key: str, data: dict[str, Any]) -> None:
    """Write a non-expiring record. Used for app-level state (e.g. config overrides)."""
    if _use_dynamodb():
        table = _get_table()
        # Set a very long TTL (~10 years) so TTL-based cleanup never touches it
        table.put_item(Item={
            "session_id": key,
            "data": json.dumps(data),
            "expires_at": int(time.time()) + 315_360_000,
        })
        logger.debug("DynamoDB put_persistent: %s", key)
    else:
        _memory_store[key] = {"data": data, "expires_at": time.time() + 315_360_000}


def get_persistent(key: str) -> dict[str, Any] | None:
    """Read a non-expiring record. Returns None if missing."""
    if _use_dynamodb():
        table = _get_table()
        resp = table.get_item(Key={"session_id": key})
        item = resp.get("Item")
        if not item:
            return None
        return json.loads(item["data"])
    entry = _memory_store.get(key)
    return entry["data"] if entry else None


def get_session(session_id: str) -> dict[str, Any] | None:
    if _use_dynamodb():
        table = _get_table()
        resp = table.get_item(Key={"session_id": session_id})
        item = resp.get("Item")
        if not item:
            return None
        # DynamoDB TTL deletion is eventual; enforce expiry manually
        if int(time.time()) > item.get("expires_at", 0):
            logger.debug("DynamoDB session expired: %s", session_id)
            delete_session(session_id)
            return None
        return json.loads(item["data"])
    else:
        entry = _memory_store.get(session_id)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del _memory_store[session_id]
            return None
        return entry["data"]


def delete_session(session_id: str) -> None:
    if _use_dynamodb():
        _get_table().delete_item(Key={"session_id": session_id})
    else:
        _memory_store.pop(session_id, None)


def put_token(session_id: str, token: str, ttl_seconds: int = 3600) -> None:
    put_session(f"token:{session_id}", {"token": token}, ttl_seconds=ttl_seconds)


def get_token(session_id: str) -> str | None:
    data = get_session(f"token:{session_id}")
    return data["token"] if data else None


def delete_token(session_id: str) -> None:
    delete_session(f"token:{session_id}")
