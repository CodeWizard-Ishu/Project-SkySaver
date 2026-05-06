"""api/main.py — SkySaver FastAPI Application Factory.

Routers mounted:
  /api/v1/scrape   <- api/routes/scrape.py
  /api/v1/routes   <- api/routes/routes.py
  /api/v1/prices   <- api/routes/prices.py
  /api/v1/alerts   <- api/routes/alerts.py
  /api/v1/status   <- api/routes/status.py  (auth endpoints)
  /api/v1/pipeline <- agents/pipeline.router (Phase 3 stub, mounted as-is)
  /health          <- api/routes/status.py  (no-auth health check)

Startup:
  - load_env() validates all required env vars
  - initialise_database() ensures schema exists
  - app.state.started_at is set for uptime tracking

Exception handlers:
  - HTTPException       -> APIResponse(success=False, error=detail)
  - RequestValidationError -> 422 APIResponse with validation errors
  - Exception (catch-all) -> 500 APIResponse, full traceback logged

Middleware stack (applied bottom-up, last-added runs first):
  1. RequestIDMiddleware (custom)   — generates/attaches request_id
  2. GZipMiddleware                 — compresses large responses (>=1000 bytes)
  CORS is intentionally OMITTED (API is localhost-only: n8n + systemd).
"""

from __future__ import annotations

import logging
import os
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from api.schemas import APIResponse

_log = logging.getLogger("flight_agent.api")

# ─── MIDDLEWARE ───────────────────────────────────────────────────────────────


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a UUID4 request_id to every request and response.

    1. Generates request_id at request ingress.
    2. Stores it on request.state.request_id for downstream use.
    3. Logs method + path + status_code + duration_ms.
    4. Adds X-Request-ID header to every response.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        t_start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - t_start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id

        _log.info(
            '{"event":"http_request","method":"%s","path":"%s",'
            '"status":%d,"duration_ms":%s,"request_id":"%s"}',
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response


# ─── APPLICATION FACTORY ─────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Create and return a fully configured FastAPI instance.

    Called once at startup by gunicorn (preload_app=True means this is called
    in the master process before forking workers).
    """
    environment = os.getenv("ENVIRONMENT", "development")
    is_production = environment == "production"

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Handle startup and shutdown events."""
        # ── Startup ───────────────────────────────────────────────────────
        try:
            from agents.base_agent import load_env
            load_env()
        except RuntimeError as exc:
            _log.critical('{"event":"startup_env_error","error":"%s"}', exc)
            raise

        try:
            from db.init_db import create_tables
            create_tables()
        except Exception as exc:
            _log.critical('{"event":"startup_db_error","error":"%s"}', exc)
            raise

        app.state.started_at = datetime.now(timezone.utc)
        _log.info('{"event":"api_started","environment":"%s"}', environment)

        yield  # ← application runs here

        # ── Shutdown ──────────────────────────────────────────────────────
        try:
            from db.queries import close_connection
            close_connection()
        except Exception:
            pass
        _log.info('{"event":"api_shutdown"}')

    app = FastAPI(
        title="SkySaver Flight Price AI Agent",
        description="REST API for the SkySaver personal flight price monitoring system.",
        version="1.0.0",
        lifespan=lifespan,
        # Disable interactive docs in production (security hardening)
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    # ── Middleware (registered bottom-up; last-added = outermost wrapper) ─────
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(RequestIDMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Return all HTTP errors in the standard APIResponse envelope."""
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        body = APIResponse(
            success=False,
            data=None,
            error=str(exc.detail),
            request_id=request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(body),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return Pydantic validation errors in the standard envelope."""
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # Flatten validation errors into a readable string
        errors = "; ".join(
            f"{' -> '.join(str(l) for l in e['loc'])}: {e['msg']}"
            for e in exc.errors()
        )
        body = APIResponse(
            success=False,
            data=None,
            error=f"Validation error: {errors}",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(body),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler — log full traceback, return 500 envelope."""
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        _log.error(
            '{"event":"unhandled_exception","request_id":"%s","error":"%s","traceback":"%s"}',
            request_id,
            str(exc),
            traceback.format_exc().replace('"', "'"),
        )
        body = APIResponse(
            success=False,
            data=None,
            error="Internal server error. Check server logs for details.",
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(body),
        )

    # ── Mount routers ─────────────────────────────────────────────────────────
    from api.routes.scrape import router as scrape_router
    from api.routes.routes import router as routes_router
    from api.routes.prices import router as prices_router
    from api.routes.alerts import router as alerts_router
    from api.routes.status import router as status_router
    from api.routes.status import health_router

    app.include_router(scrape_router, prefix="/api/v1")
    app.include_router(routes_router, prefix="/api/v1")
    app.include_router(prices_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(status_router, prefix="/api/v1")
    app.include_router(health_router)  # /health — no prefix

    # Mount Phase 3 pipeline router as-is (stub from agents/pipeline.py)
    try:
        from agents.pipeline import router as pipeline_router
        if pipeline_router is not None:
            app.include_router(pipeline_router, prefix="/api/v1")
    except (ImportError, AttributeError):
        _log.warning('{"event":"pipeline_router_not_available"}')

    return app
