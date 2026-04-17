from __future__ import annotations
import os
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from botocore.exceptions import ClientError, NoCredentialsError, TokenRetrievalError
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from argus.api.routers import queries, catalog, workgroups
from argus.api.routers import config as config_router
from argus.api.routers import export, auth
from argus.api.dependencies import set_config_path


STATIC_DIR = Path(__file__).parent / "static"

_AUTH_ERROR_CODES = {
    "ExpiredTokenException",
    "ExpiredToken",
    "TokenRefreshRequired",
    "InvalidClientTokenId",
    "AuthFailure",
    "RequestExpired",
}

# Substrings that indicate an auth/token expiry even when wrapped in a generic exception
_AUTH_ERROR_STRINGS = (
    "token has expired",
    "expired and refresh failed",
    "error retrieving token from sso",
    "error when retrieving token from sso",
    "sso token",
    "invalidclienttokenid",
    "expiredtokenexception",
    "no credentials",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app(config_path: Optional[Path] = None) -> FastAPI:
    set_config_path(config_path)

    app = FastAPI(
        title="Argus for Athena API",
        description="AWS Athena DBMS — REST API",
        version="0.1.0",
        lifespan=lifespan,
    )

    def _auth_expired_response(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": detail, "error_type": "auth_expired"},
        )

    @app.exception_handler(NoCredentialsError)
    async def no_credentials_handler(request: Request, exc: NoCredentialsError):
        return _auth_expired_response("No AWS credentials found.")

    @app.exception_handler(ClientError)
    async def client_error_handler(request: Request, exc: ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in _AUTH_ERROR_CODES:
            return _auth_expired_response(f"AWS session expired ({code}).")
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(TokenRetrievalError)
    async def token_retrieval_handler(request: Request, exc: TokenRetrievalError):
        return _auth_expired_response("AWS token retrieval failed.")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Promote auth-related errors that were caught and re-raised as 400s by route handlers."""
        if exc.status_code in (400, 403):
            detail_lower = str(exc.detail).lower()
            if any(s in detail_lower for s in _AUTH_ERROR_STRINGS):
                return _auth_expired_response(str(exc.detail))
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    _default_local_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    _cors_env = os.environ.get("ARGUS_CORS_ORIGINS", "")
    if _cors_env:
        cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
    elif os.environ.get("LAMBDA_RUNTIME"):
        cors_origins = ["*"]
    else:
        cors_origins = _default_local_origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(queries.router, prefix="/api/v1")
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(workgroups.router, prefix="/api/v1")
    app.include_router(config_router.router, prefix="/api/v1")
    app.include_router(export.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")

    if not os.environ.get("LAMBDA_RUNTIME") and STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    config_path: Optional[Path] = None,
    open_browser: bool = False,
    reload: bool = False,
):
    app = create_app(config_path)
    if open_browser:
        import threading
        def _open():
            import time
            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=_open, daemon=True).start()
    uvicorn.run(app, host=host, port=port, reload=reload)
