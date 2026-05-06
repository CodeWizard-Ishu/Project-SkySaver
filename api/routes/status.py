"""api/routes/status.py — System health and status endpoints.

Two separate routers are exported:
  health_router  — /health    (no auth, used by systemd + nginx)
  router         — /api/v1/status (requires API key)

health_router is mounted without prefix in api/main.py.
router is mounted with /api/v1 prefix.

All blocking operations (DB probe, file stat, model listing) are wrapped
in run_in_executor.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.dependencies import ApiKeyDep, RequestIdDep
from api.schemas import HealthResponse, SystemStatusResponse, success_response

_log = logging.getLogger("flight_agent.api.status")

_API_VERSION = "1.0.0"

# ─── Health router (no auth) ──────────────────────────────────────────────────
health_router = APIRouter(tags=["health"])

# ─── Status router (auth required) ───────────────────────────────────────────
router = APIRouter(prefix="/status", tags=["status"])


# ─── GET /health ──────────────────────────────────────────────────────────────


@health_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Lightweight liveness probe used by systemd and nginx. No auth required.",
)
async def health_check(request: Request) -> JSONResponse:
    """GET /health — no authentication required."""
    started_at: Optional[datetime] = getattr(
        request.app.state, "started_at", None
    )
    uptime = 0.0
    if started_at is not None:
        uptime = (datetime.now(timezone.utc) - started_at).total_seconds()

    payload = HealthResponse(
        status="ok",
        version=_API_VERSION,
        uptime_seconds=round(uptime, 2),
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(payload),
    )


# ─── GET /api/v1/status ───────────────────────────────────────────────────────


def _collect_status_sync() -> dict:
    """Collect full system status synchronously. Called in run_in_executor."""
    import db.queries as queries
    from agents.rate_limiter import RateLimiter

    db_path_str = os.getenv("DATABASE_PATH", "./db/flight_prices.db")
    db_path = Path(db_path_str)

    # ── DB health check ──────────────────────────────────────────────────────
    database_ok = False
    database_size_mb = 0.0
    total_observations = 0
    total_routes_monitored = 0
    total_alerts_sent = 0
    last_scrape_at: Optional[str] = None
    last_alert_at: Optional[str] = None

    try:
        conn = queries.get_connection()
        conn.execute("SELECT 1").fetchone()
        database_ok = True

        # File size
        if db_path.exists():
            database_size_mb = round(db_path.stat().st_size / (1024 * 1024), 3)

        # Observation count
        row = conn.execute("SELECT COUNT(*) FROM flight_prices").fetchone()
        total_observations = row[0] if row else 0

        # Monitored routes count (all, including paused)
        row = conn.execute("SELECT COUNT(*) FROM monitored_routes").fetchone()
        total_routes_monitored = row[0] if row else 0

        # Alert count
        row = conn.execute("SELECT COUNT(*) FROM alert_log").fetchone()
        total_alerts_sent = row[0] if row else 0

        # Last scrape time
        row = conn.execute(
            "SELECT observed_at FROM flight_prices ORDER BY observed_at DESC LIMIT 1"
        ).fetchone()
        last_scrape_at = row["observed_at"] if row else None

        # Last alert time
        row = conn.execute(
            "SELECT alerted_at FROM alert_log ORDER BY alerted_at DESC LIMIT 1"
        ).fetchone()
        last_alert_at = row["alerted_at"] if row else None

    except Exception as exc:
        _log.error('{"event":"status_db_check_failed","error":"%s"}', exc)

    # ── ML model check ────────────────────────────────────────────────────────
    models_dir = Path("models")
    pkl_files = sorted(models_dir.glob("*.pkl")) if models_dir.exists() else []
    ml_model_exists = len(pkl_files) > 0
    ml_model_version = pkl_files[-1].name if pkl_files else "none"

    # ── Rate limits ───────────────────────────────────────────────────────────
    try:
        rate_limits = RateLimiter().get_status()
    except Exception as exc:
        _log.error('{"event":"status_rate_limiter_failed","error":"%s"}', exc)
        rate_limits = {}

    return {
        "api_version": _API_VERSION,
        "database_ok": database_ok,
        "database_path": db_path_str,
        "database_size_mb": database_size_mb,
        "total_observations": total_observations,
        "total_routes_monitored": total_routes_monitored,
        "total_alerts_sent": total_alerts_sent,
        "rate_limits": rate_limits,
        "ml_model_exists": ml_model_exists,
        "ml_model_version": ml_model_version,
        "last_scrape_at": last_scrape_at,
        "last_alert_at": last_alert_at,
    }


@router.get(
    "",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Full system status",
    description=(
        "Returns comprehensive system health: DB status, observation counts, "
        "ML model info, rate limits, and uptime. Requires X-SkySaver-Key header."
    ),
)
async def get_system_status(
    request: Request,
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """GET /api/v1/status."""
    started_at: Optional[datetime] = getattr(request.app.state, "started_at", None)
    uptime = 0.0
    if started_at is not None:
        uptime = (datetime.now(timezone.utc) - started_at).total_seconds()

    loop = asyncio.get_event_loop()
    try:
        status_data = await loop.run_in_executor(None, _collect_status_sync)
    except Exception as exc:
        _log.error('{"event":"status_collect_failed","error":"%s"}', exc)
        status_data = {
            "api_version": _API_VERSION,
            "database_ok": False,
            "database_path": "",
            "database_size_mb": 0.0,
            "total_observations": 0,
            "total_routes_monitored": 0,
            "total_alerts_sent": 0,
            "rate_limits": {},
            "ml_model_exists": False,
            "ml_model_version": "none",
            "last_scrape_at": None,
            "last_alert_at": None,
        }

    status_data["uptime_seconds"] = round(uptime, 2)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(status_data, request_id)),
    )
