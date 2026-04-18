"""Sanitized HTTP error responses.

Raw AWS SDK errors often leak internal details (account IDs, role ARNs, bucket
names, stack traces). This module provides helpers that log the full exception
server-side but return generic, non-identifying messages to clients with a
request id for correlation.

Disable sanitization (useful for local development) by setting
``ARGUS_VERBOSE_ERRORS=true`` in the environment.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

from fastapi import HTTPException


log = logging.getLogger(__name__)


def _verbose_errors_enabled() -> bool:
    return os.environ.get("ARGUS_VERBOSE_ERRORS", "").lower() in ("1", "true", "yes")


def sanitize_error(
    exc: Exception,
    *,
    status_code: int = 400,
    public_message: str = "Request failed",
    context: Optional[str] = None,
) -> HTTPException:
    """Return an HTTPException with a sanitized ``detail``.

    The full exception (message + traceback) is logged server-side with a
    generated request_id. The client receives only ``public_message`` plus the
    same request_id so operators can correlate reports without having to guess.

    When ``ARGUS_VERBOSE_ERRORS=true`` the raw exception message is included
    in the response — useful for local development only.
    """
    request_id = uuid.uuid4().hex[:12]
    log.exception(
        "HTTPException %s [%s] %s: %s",
        status_code, request_id, context or public_message, exc,
    )
    if _verbose_errors_enabled():
        detail = f"{public_message}: {exc} (request_id={request_id})"
    else:
        detail = f"{public_message} (request_id={request_id})"
    return HTTPException(status_code=status_code, detail=detail)
