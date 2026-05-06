"""api/routes/prices.py — Price history and statistics endpoints.

Endpoints:
  GET /api/v1/prices/{route}         — full price history + stats for a route+date
  GET /api/v1/prices/{route}/latest  — most recent single observation

Path param: route must match ^[A-Z]{3}-[A-Z]{3}$ (validated via regex in handler).
Query param: travel_date (ISO date, required for both endpoints).
Query param: days_back (int, default=30, max=365) for history filtering.
Query param: source (optional) to filter by data source.

All blocking DB calls are wrapped in run_in_executor.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.dependencies import ApiKeyDep, RequestIdDep
from api.schemas import (
    PriceHistoryResponse,
    PriceObservationResponse,
    PriceStatsResponse,
    error_response,
    success_response,
)

_log = logging.getLogger("flight_agent.api.prices")

router = APIRouter(prefix="/prices", tags=["prices"])

_ROUTE_RE = re.compile(r"^[A-Z]{3}-[A-Z]{3}$")
_VALID_SOURCES = frozenset({"skyscanner", "google_flights", "amadeus"})
_MIN_STATS_OBSERVATIONS = 5


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _validate_route(route: str) -> None:
    if not _ROUTE_RE.match(route):
        raise ValueError(
            f"Route '{route}' must be in XXX-YYY format (three uppercase IATA codes)."
        )


def _obs_to_response(obs) -> dict:
    """Convert a PriceObservation dataclass to a serialisable dict."""
    observed_at = obs.observed_at
    if isinstance(observed_at, datetime):
        observed_at = (
            observed_at.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
    return {
        "observed_at": observed_at,
        "price_inr": obs.price_inr,
        "airline": obs.airline,
        "stops": obs.stops,
        "source": obs.source,
        "days_advance": obs.days_advance,
    }


def _fetch_price_history(
    route: str,
    travel_date: date,
    days_back: int,
    source: Optional[str],
) -> dict:
    """Synchronous DB fetch — called inside run_in_executor."""
    import db.queries as queries

    observations = queries.get_price_history(
        route=route,
        travel_date=travel_date,
        days_back=days_back,
        source=source,
    )

    stats = queries.get_price_stats(route, travel_date)
    stats_response: Optional[dict] = None

    if stats is not None and stats.observation_count >= _MIN_STATS_OBSERVATIONS:
        last_updated = stats.last_updated
        if isinstance(last_updated, datetime):
            last_updated = (
                last_updated.astimezone(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
        stats_response = {
            "p10": stats.p10_price,
            "p25": stats.p25_price,
            "median": stats.median_price,
            "p75": None,   # not stored in current schema; computed on demand if needed
            "p90": None,
            "all_time_low": stats.all_time_low,
            "all_time_high": stats.all_time_high,
            "observation_count": stats.observation_count,
            "last_updated": last_updated,
        }

    return {
        "route": route,
        "travel_date": travel_date.isoformat(),
        "stats": stats_response,
        "observations": [_obs_to_response(o) for o in observations],
        "observation_count": len(observations),
    }


def _fetch_latest_price(route: str, travel_date: date) -> Optional[dict]:
    """Fetch the single most recent observation. Returns None if no data."""
    import db.queries as queries

    history = queries.get_price_history(route=route, travel_date=travel_date, days_back=365)
    if not history:
        return None
    latest = history[-1]  # list is ordered ASC; last = most recent
    return _obs_to_response(latest)


# ─── GET /api/v1/prices/{route} ───────────────────────────────────────────────


@router.get(
    "/{route}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Get price history for a route",
    description=(
        "Returns all price observations and computed statistics for a route+date "
        "combination within the specified lookback window."
    ),
)
async def get_price_history(
    route: str,
    _: ApiKeyDep,
    request_id: RequestIdDep,
    travel_date: str = Query(..., description="ISO date string e.g. 2026-12-15"),
    days_back: int = Query(default=30, ge=1, le=365, description="Days of history to return"),
    source: Optional[str] = Query(default=None, description="Filter by source: skyscanner|google_flights|amadeus"),
) -> JSONResponse:
    """GET /api/v1/prices/{route}."""
    # Validate route format
    try:
        _validate_route(route)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # Validate travel_date
    try:
        td = date.fromisoformat(travel_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid travel_date '{travel_date}'. Expected YYYY-MM-DD.",
        )

    # Validate source filter
    if source is not None and source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid source '{source}'. Must be one of: {sorted(_VALID_SOURCES)}",
        )

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None, _fetch_price_history, route, td, days_back, source
        )
    except Exception as exc:
        _log.error(
            '{"event":"price_history_error","route":"%s","error":"%s"}',
            route, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch price history: {exc}",
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(result, request_id)),
    )


# ─── GET /api/v1/prices/{route}/latest ───────────────────────────────────────


@router.get(
    "/{route}/latest",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Get latest price observation for a route",
    description="Returns the most recent single price observation for a route+date pair.",
)
async def get_latest_price(
    route: str,
    _: ApiKeyDep,
    request_id: RequestIdDep,
    travel_date: str = Query(..., description="ISO date string e.g. 2026-12-15"),
) -> JSONResponse:
    """GET /api/v1/prices/{route}/latest."""
    try:
        _validate_route(route)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    try:
        td = date.fromisoformat(travel_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid travel_date '{travel_date}'. Expected YYYY-MM-DD.",
        )

    loop = asyncio.get_event_loop()
    try:
        latest = await loop.run_in_executor(None, _fetch_latest_price, route, td)
    except Exception as exc:
        _log.error(
            '{"event":"latest_price_error","route":"%s","error":"%s"}',
            route, exc
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch latest price: {exc}",
        )

    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No price observations found for route '{route}' on {travel_date}.",
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(latest, request_id)),
    )
