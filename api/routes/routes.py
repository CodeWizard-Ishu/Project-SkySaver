"""api/routes/routes.py — Monitored routes CRUD endpoints.

Endpoints:
  GET    /api/v1/routes               — list all active monitored routes
  POST   /api/v1/routes               — add/upsert a monitored route
  DELETE /api/v1/routes/{route}       — soft-delete (pause) a route
  PUT    /api/v1/routes/{route}/resume — resume a paused route

DB calls are blocking (SQLite). All are wrapped in run_in_executor.
Historical price data is NEVER deleted on pause/resume.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.dependencies import ApiKeyDep, RequestIdDep
from api.schemas import (
    AddRouteRequest,
    MonitoredRouteResponse,
    error_response,
    success_response,
)

_log = logging.getLogger("flight_agent.api.routes")

router = APIRouter(prefix="/routes", tags=["routes"])


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _get_routes_sync(include_paused: bool = False) -> list[dict]:
    """Fetch monitored routes from DB synchronously."""
    import db.queries as queries
    import sqlite3

    conn = queries.get_connection()
    if include_paused:
        rows = conn.execute(
            "SELECT route, travel_dates, active, created_at FROM monitored_routes"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT route, travel_dates, active, created_at FROM monitored_routes WHERE active=1"
        ).fetchall()

    obs_counts = queries.get_observation_count_by_route()

    result = []
    for r in rows:
        try:
            dates = json.loads(r["travel_dates"])
        except (json.JSONDecodeError, TypeError):
            dates = []
        result.append({
            "route": r["route"],
            "travel_dates": dates,
            "is_active": bool(r["active"]),
            "created_at": r["created_at"],
            "observation_count": obs_counts.get(r["route"], 0),
        })
    return result


def _add_route_sync(route: str, travel_dates: list[str]) -> dict:
    """Upsert a monitored route and return its details."""
    import db.queries as queries

    queries.upsert_monitored_route(route=route, travel_dates=travel_dates)
    # Re-fetch to return the stored record
    conn = queries.get_connection()
    row = conn.execute(
        "SELECT route, travel_dates, active, created_at FROM monitored_routes WHERE route=?",
        (route,),
    ).fetchone()
    obs_counts = queries.get_observation_count_by_route()
    try:
        dates = json.loads(row["travel_dates"])
    except (json.JSONDecodeError, TypeError):
        dates = travel_dates
    return {
        "route": row["route"],
        "travel_dates": dates,
        "is_active": bool(row["active"]),
        "created_at": row["created_at"],
        "observation_count": obs_counts.get(route, 0),
    }


def _set_route_active_sync(route: str, active: bool) -> dict:
    """Set a route's active flag. Raises RouteNotFoundError if missing."""
    import db.queries as queries

    conn = queries.get_connection()
    row = conn.execute(
        "SELECT route FROM monitored_routes WHERE route=?", (route,)
    ).fetchone()
    if row is None:
        raise queries.RouteNotFoundError(f"Route '{route}' not found in monitored routes.")

    import sqlite3
    from db.queries import _write_lock

    with _write_lock:
        with conn:
            conn.execute(
                "UPDATE monitored_routes SET active=? WHERE route=?",
                (1 if active else 0, route),
            )
    # Re-fetch updated row
    updated = conn.execute(
        "SELECT route, travel_dates, active, created_at FROM monitored_routes WHERE route=?",
        (route,),
    ).fetchone()
    obs_counts = queries.get_observation_count_by_route()
    try:
        dates = json.loads(updated["travel_dates"])
    except (json.JSONDecodeError, TypeError):
        dates = []
    return {
        "route": updated["route"],
        "travel_dates": dates,
        "is_active": bool(updated["active"]),
        "created_at": updated["created_at"],
        "observation_count": obs_counts.get(route, 0),
    }


# ─── GET /api/v1/routes ───────────────────────────────────────────────────────


@router.get(
    "",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="List monitored routes",
    description="Returns all active monitored routes. Pass ?include_paused=true to also return paused routes.",
)
async def list_routes(
    _: ApiKeyDep,
    request_id: RequestIdDep,
    include_paused: bool = False,
) -> JSONResponse:
    """GET /api/v1/routes."""
    loop = asyncio.get_event_loop()
    routes = await loop.run_in_executor(None, _get_routes_sync, include_paused)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(routes, request_id)),
    )


# ─── POST /api/v1/routes ──────────────────────────────────────────────────────


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Add a monitored route",
    description="Add or update a route to monitor. Duplicate routes are safely upserted.",
)
async def add_route(
    body: AddRouteRequest,
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """POST /api/v1/routes."""
    loop = asyncio.get_event_loop()
    try:
        route_data = await loop.run_in_executor(
            None, _add_route_sync, body.route, body.travel_dates
        )
    except Exception as exc:
        _log.error('{"event":"add_route_error","route":"%s","error":"%s"}', body.route, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add route: {exc}",
        )

    _log.info('{"event":"route_added","route":"%s","request_id":"%s"}', body.route, request_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(route_data, request_id)),
    )


# ─── DELETE /api/v1/routes/{route} ───────────────────────────────────────────


@router.delete(
    "/{route}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Pause a monitored route",
    description="Soft-deletes a route (sets is_active=False). Historical price data is preserved.",
)
async def pause_route(
    route: str,
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """DELETE /api/v1/routes/{route} — soft-pause."""
    from db.queries import RouteNotFoundError
    loop = asyncio.get_event_loop()
    try:
        route_data = await loop.run_in_executor(None, _set_route_active_sync, route, False)
    except RouteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route}' not found in monitored routes.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause route: {exc}",
        )

    _log.info('{"event":"route_paused","route":"%s","request_id":"%s"}', route, request_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(route_data, request_id)),
    )


# ─── PUT /api/v1/routes/{route}/resume ───────────────────────────────────────


@router.put(
    "/{route}/resume",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Resume a paused route",
    description="Sets is_active=True for a previously paused route.",
)
async def resume_route(
    route: str,
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """PUT /api/v1/routes/{route}/resume."""
    from db.queries import RouteNotFoundError
    loop = asyncio.get_event_loop()
    try:
        route_data = await loop.run_in_executor(None, _set_route_active_sync, route, True)
    except RouteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route}' not found in monitored routes.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume route: {exc}",
        )

    _log.info('{"event":"route_resumed","route":"%s","request_id":"%s"}', route, request_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(route_data, request_id)),
    )
