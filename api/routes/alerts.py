"""api/routes/alerts.py — Alert log query endpoints.

Endpoints:
  GET /api/v1/alerts                     — paginated alert history
  GET /api/v1/alerts/cooldown/{route}    — check if route is in alert cooldown

The alert_log table stores one row per sent alert. The schema does NOT have
separate urgency_score / p10_at_alert / pct_below_median / telegram_delivered
columns — these are derived or defaulted from existing schema columns
(price_notified, alert_reason, alerted_at) for API compatibility.

All blocking DB calls are wrapped in run_in_executor.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.dependencies import ApiKeyDep, RequestIdDep
from api.schemas import success_response

_log = logging.getLogger("flight_agent.api.alerts")

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _fetch_alerts(
    route_filter: Optional[str],
    limit: int,
    offset: int,
) -> dict:
    """Fetch paginated alerts from alert_log. Called inside run_in_executor."""
    import db.queries as queries

    conn = queries.get_connection()

    # Get total count
    if route_filter:
        total_row = conn.execute(
            "SELECT COUNT(*) FROM alert_log WHERE route=?",
            (route_filter,),
        ).fetchone()
    else:
        total_row = conn.execute("SELECT COUNT(*) FROM alert_log").fetchone()
    total_count: int = total_row[0] if total_row else 0

    # Fetch paginated rows
    if route_filter:
        rows = conn.execute(
            """SELECT id, route, travel_date, price_notified, alert_reason, alerted_at
               FROM alert_log WHERE route=?
               ORDER BY alerted_at DESC
               LIMIT ? OFFSET ?""",
            (route_filter, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, route, travel_date, price_notified, alert_reason, alerted_at
               FROM alert_log
               ORDER BY alerted_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()

    alerts = []
    for r in rows:
        alerts.append({
            "alert_id": r["id"],
            "route": r["route"],
            "travel_date": r["travel_date"],
            "price_at_alert": r["price_notified"],
            # Derive fields not present in the DB schema
            "p10_at_alert": None,               # not stored in current schema
            "pct_below_median": None,           # not stored in current schema
            "recommendation": r["alert_reason"] or "Buy now — price is at a historical low.",
            "urgency_score": 8,                 # default urgency; Phase 5 will store this
            "sent_at": r["alerted_at"],
            "telegram_delivered": True,          # stored alerts = delivered
        })

    return {
        "alerts": alerts,
        "total_count": total_count,
        "has_more": (offset + limit) < total_count,
    }


def _check_cooldown_sync(route: str) -> dict:
    """Check alert cooldown for a route. Called inside run_in_executor.

    Queries alert_log directly for the most recent alert for this route
    (any travel_date) to determine if the 24-hour cooldown is active.
    """
    import db.queries as queries
    from datetime import timedelta

    COOLDOWN_HOURS = 24
    conn = queries.get_connection()
    row = conn.execute(
        "SELECT alerted_at FROM alert_log WHERE route=? ORDER BY alerted_at DESC LIMIT 1",
        (route,),
    ).fetchone()

    if row is None:
        return {"route": route, "in_cooldown": False, "cooldown_expires_at": None}

    alerted_at = datetime.fromisoformat(row["alerted_at"].replace("Z", "+00:00"))
    hours_since = (datetime.now(timezone.utc) - alerted_at).total_seconds() / 3600.0
    in_cooldown = hours_since < COOLDOWN_HOURS

    cooldown_expires_at: Optional[str] = None
    if in_cooldown:
        expires = alerted_at + timedelta(hours=COOLDOWN_HOURS)
        cooldown_expires_at = (
            expires.isoformat(timespec="seconds").replace("+00:00", "Z")
        )

    return {
        "route": route,
        "in_cooldown": in_cooldown,
        "cooldown_expires_at": cooldown_expires_at,
    }


# ─── GET /api/v1/alerts ───────────────────────────────────────────────────────


@router.get(
    "",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Get alert history",
    description="Returns paginated alert log. Use ?route=NAG-DEL to filter by route.",
)
async def get_alerts(
    _: ApiKeyDep,
    request_id: RequestIdDep,
    route: Optional[str] = Query(default=None, description="Filter alerts by route e.g. NAG-DEL"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> JSONResponse:
    """GET /api/v1/alerts."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _fetch_alerts, route, limit, offset)
    except Exception as exc:
        _log.error('{"event":"alerts_fetch_error","error":"%s"}', exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch alerts: {exc}",
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(result, request_id)),
    )


# ─── GET /api/v1/alerts/cooldown/{route} ─────────────────────────────────────


@router.get(
    "/cooldown/{route}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Check alert cooldown for a route",
    description="Returns whether a route is currently in the 24-hour alert cooldown window.",
)
async def check_cooldown(
    route: str,
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """GET /api/v1/alerts/cooldown/{route}."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _check_cooldown_sync, route)
    except Exception as exc:
        _log.error('{"event":"cooldown_check_error","route":"%s","error":"%s"}', route, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check cooldown: {exc}",
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(result, request_id)),
    )
