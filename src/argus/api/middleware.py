from __future__ import annotations
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from argus.core.audit_logger import audit_logger, _classify_action


class AuditMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that writes one audit record per HTTP request.

    Completely transparent when audit logging is disabled — the middleware is
    always registered but ``audit_logger.log_action`` is a no-op unless
    ``ARGUS_AUDIT_LOGGING=true``.

    Skips health-check / static / docs paths to avoid noise.
    """

    _SKIP_PREFIXES = ("/docs", "/openapi", "/redoc", "/healthz", "/static")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if any(request.url.path.startswith(p) for p in self._SKIP_PREFIXES):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        # Extract user identity from the SSO credential-id header (Lambda mode)
        # or fall back to "anonymous" for unauthenticated requests.
        user = (
            getattr(request.state, "user_identity", None)
            or request.headers.get("x-credential-id", "anonymous")
        )

        # Optional context extracted from query parameters (never from body).
        database    = request.query_params.get("database")
        workgroup   = request.query_params.get("workgroup")
        request_id  = request.headers.get("x-request-id")

        audit_logger.log_action(
            user_identity=user,
            action_type=_classify_action(request.method, request.url.path),
            http_method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            database=database,
            workgroup=workgroup,
        )

        return response
