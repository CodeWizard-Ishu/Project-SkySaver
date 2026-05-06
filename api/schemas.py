"""api/schemas.py — Pydantic v2 request/response models for SkySaver API.

All models follow these conventions:
  - Request models: ConfigDict(str_strip_whitespace=True)
  - Response models: ConfigDict(from_attributes=True)  (ORM-compatible)
  - No Pydantic v1 syntax (.dict(), orm_mode=True, @validator)
  - All validators use @field_validator with descriptive error messages

The APIResponse envelope is returned by EVERY endpoint.
Helper functions success_response() and error_response() are used by all
route handlers to ensure consistent serialisation.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── UTILITIES ────────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    """Return current UTC time as ISO-8601 string ending in Z."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


# ─── BASE ENVELOPE ───────────────────────────────────────────────────────────


class APIResponse(BaseModel):
    """Universal response envelope returned by every SkySaver API endpoint.

    On success: success=True, data=<payload>, error=None
    On failure: success=False, data=None, error=<message>
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=_utcnow_iso)
    request_id: str = Field(default_factory=lambda: str(uuid4()))


def success_response(data: Any, request_id: str) -> APIResponse:
    """Build a success APIResponse with data payload."""
    return APIResponse(success=True, data=data, request_id=request_id)


def error_response(error: str, request_id: str) -> APIResponse:
    """Build a failure APIResponse with error message."""
    return APIResponse(success=False, error=error, request_id=request_id)


# ─── SCRAPE SCHEMAS ───────────────────────────────────────────────────────────


class ScrapeRunRequest(BaseModel):
    """Optional body for POST /api/v1/scrape/run."""

    model_config = ConfigDict(str_strip_whitespace=True)

    routes: Optional[list[str]] = None
    """If provided, only scrape these specific routes (e.g. ["NAG-DEL"])."""

    dry_run: bool = False
    """If True: scrape and forecast but skip sending Telegram alerts."""

    @field_validator("routes")
    @classmethod
    def validate_route_formats(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        pattern = re.compile(r"^[A-Z]{3}-[A-Z]{3}$")
        for route in v:
            if not pattern.match(route):
                raise ValueError(
                    f"Route '{route}' must be in XXX-YYY format (uppercase IATA codes)."
                )
        return v


class ScrapeRunResponse(BaseModel):
    """Data payload for POST /api/v1/scrape/run response."""

    model_config = ConfigDict(from_attributes=True)

    routes_attempted: int
    routes_succeeded: int
    routes_failed: int
    total_fares_scraped: int
    alerts_sent: int
    retrain_triggered: bool
    duration_seconds: float
    errors: list[str]


# ─── ROUTE SCHEMAS ────────────────────────────────────────────────────────────


class AddRouteRequest(BaseModel):
    """Request body for POST /api/v1/routes."""

    model_config = ConfigDict(str_strip_whitespace=True)

    route: str
    """Route in 'XXX-YYY' IATA format, e.g. 'NAG-DEL'."""

    travel_dates: list[str]
    """List of ISO date strings for travel dates, e.g. ['2026-12-15']."""

    @field_validator("route")
    @classmethod
    def validate_route_format(cls, v: str) -> str:
        if not re.match(r"^[A-Z]{3}-[A-Z]{3}$", v):
            raise ValueError(
                f"Route '{v}' must be in XXX-YYY format (three uppercase IATA codes on each side)."
            )
        return v

    @field_validator("travel_dates")
    @classmethod
    def validate_dates_future(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("travel_dates must contain at least one date.")
        today = date.today()
        for d_str in v:
            try:
                parsed = date.fromisoformat(d_str)
            except ValueError:
                raise ValueError(
                    f"'{d_str}' is not a valid ISO date (expected YYYY-MM-DD)."
                )
            if parsed <= today:
                raise ValueError(
                    f"Travel date '{d_str}' must be in the future (today is {today})."
                )
        return v


class MonitoredRouteResponse(BaseModel):
    """A single monitored route entry returned by the routes endpoints."""

    model_config = ConfigDict(from_attributes=True)

    route: str
    travel_dates: list[str]
    is_active: bool
    created_at: str
    observation_count: int


# ─── PRICE SCHEMAS ────────────────────────────────────────────────────────────


class PriceObservationResponse(BaseModel):
    """A single scraped price observation."""

    model_config = ConfigDict(from_attributes=True)

    observed_at: str
    price_inr: int
    airline: str
    stops: int
    source: str
    days_advance: int


class PriceStatsResponse(BaseModel):
    """Computed percentile statistics for a route+date pair."""

    model_config = ConfigDict(from_attributes=True)

    p10: Optional[int] = None
    p25: Optional[int] = None
    median: Optional[int] = None
    p75: Optional[int] = None
    p90: Optional[int] = None
    all_time_low: int
    all_time_high: int
    observation_count: int
    last_updated: str


class PriceHistoryResponse(BaseModel):
    """Full price history response for a route+date."""

    model_config = ConfigDict(from_attributes=True)

    route: str
    travel_date: str
    stats: Optional[PriceStatsResponse] = None
    """Null if fewer than 5 observations have been recorded."""
    observations: list[PriceObservationResponse]
    observation_count: int


# ─── ALERT SCHEMAS ────────────────────────────────────────────────────────────


class AlertEntry(BaseModel):
    """A single entry from the alert_log table."""

    model_config = ConfigDict(from_attributes=True)

    alert_id: int
    route: str
    travel_date: str
    price_at_alert: int
    p10_at_alert: Optional[int] = None
    pct_below_median: Optional[float] = None
    recommendation: str
    urgency_score: int
    sent_at: str
    telegram_delivered: bool


class AlertLogResponse(BaseModel):
    """Paginated list of alert log entries."""

    model_config = ConfigDict(from_attributes=True)

    alerts: list[AlertEntry]
    total_count: int
    has_more: bool


class AlertCooldownResponse(BaseModel):
    """Cooldown status for a specific route."""

    model_config = ConfigDict(from_attributes=True)

    route: str
    in_cooldown: bool
    cooldown_expires_at: Optional[str] = None


# ─── STATUS SCHEMAS ───────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Lightweight health check response (no auth required)."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    version: str
    uptime_seconds: float


class SystemStatusResponse(BaseModel):
    """Full system status response for GET /api/v1/status."""

    model_config = ConfigDict(from_attributes=True)

    api_version: str
    database_ok: bool
    database_path: str
    database_size_mb: float
    total_observations: int
    total_routes_monitored: int
    total_alerts_sent: int
    rate_limits: dict
    ml_model_exists: bool
    ml_model_version: str
    last_scrape_at: Optional[str] = None
    last_alert_at: Optional[str] = None
    uptime_seconds: float
