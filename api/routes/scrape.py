"""api/routes/scrape.py — Scraping trigger and status endpoints.

Endpoints:
  POST /api/v1/scrape/run         — Trigger a full pipeline run
  GET  /api/v1/scrape/last-run    — Return summary of last pipeline run
  GET  /api/v1/scrape/rate-limits — Return current API rate limit usage

All blocking operations (pipeline run, file I/O) are wrapped in
run_in_executor to avoid blocking the async event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from api.dependencies import ApiKeyDep, RequestIdDep
from api.schemas import (
    APIResponse,
    ScrapeRunRequest,
    ScrapeRunResponse,
    error_response,
    success_response,
)

_log = logging.getLogger("flight_agent.api.scrape")

router = APIRouter(prefix="/scrape", tags=["scrape"])

_LAST_RUN_PATH = Path("db/last_run.json")


# ─── POST /api/v1/scrape/run ─────────────────────────────────────────────────


def _run_pipeline_sync(dry_run: bool = False) -> ScrapeRunResponse:
    """Execute the full pipeline synchronously.

    Called inside run_in_executor so the async event loop is not blocked.
    dry_run=True scrapes and forecasts but skips alert sending.
    """
    from agents.pipeline import PipelineRunner
    import time as _time

    t_start = _time.perf_counter()
    runner = PipelineRunner()
    result = runner.run()
    duration = round(_time.perf_counter() - t_start, 2)

    # Map PipelineRunResult fields to the API response model.
    # scrape_result carries the per-source counts.
    sr = result.scrape_result
    routes_attempted = sr.routes_attempted
    routes_succeeded = sr.routes_succeeded
    routes_failed = sr.routes_failed
    total_fares_scraped = sr.total_fares_scraped

    alerts_sent = result.alerts_sent if not dry_run else 0

    return ScrapeRunResponse(
        routes_attempted=routes_attempted,
        routes_succeeded=routes_succeeded,
        routes_failed=routes_failed,
        total_fares_scraped=total_fares_scraped,
        alerts_sent=alerts_sent,
        retrain_triggered=result.retrain_triggered,
        duration_seconds=duration,
        errors=list(result.errors),
    )


@router.post(
    "/run",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger a full pipeline run",
    description=(
        "Scrapes all active monitored routes, runs ML forecasting, evaluates "
        "alert gates, and sends Telegram alerts for qualifying fares. "
        "Runs synchronously — may take 2–5 minutes. Uses run_in_executor "
        "to avoid blocking the async event loop."
    ),
)
async def trigger_scrape_run(
    _: ApiKeyDep,
    request_id: RequestIdDep,
    body: Optional[ScrapeRunRequest] = None,
) -> JSONResponse:
    """POST /api/v1/scrape/run — trigger a full pipeline run."""
    dry_run = body.dry_run if body else False

    _log.info(
        '{"event":"scrape_run_requested","dry_run":%s,"request_id":"%s"}',
        str(dry_run).lower(),
        request_id,
    )

    loop = asyncio.get_event_loop()
    try:
        scrape_response = await loop.run_in_executor(
            None, _run_pipeline_sync, dry_run
        )
    except Exception as exc:
        _log.error(
            '{"event":"scrape_run_failed","error":"%s","request_id":"%s"}',
            str(exc),
            request_id,
        )
        body_out = error_response(f"Pipeline run failed: {exc}", request_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(body_out),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(
            success_response(scrape_response.model_dump(), request_id)
        ),
    )


# ─── GET /api/v1/scrape/last-run ─────────────────────────────────────────────


def _read_last_run() -> Optional[dict]:
    """Read db/last_run.json. Returns None if file does not exist."""
    if not _LAST_RUN_PATH.exists():
        return None
    try:
        return json.loads(_LAST_RUN_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning('{"event":"last_run_read_error","error":"%s"}', exc)
        return None


@router.get(
    "/last-run",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Get last pipeline run summary",
    description="Returns the summary of the most recent pipeline run from db/last_run.json. "
                "Returns data=null if no run has been executed yet.",
)
async def get_last_run(
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """GET /api/v1/scrape/last-run."""
    loop = asyncio.get_event_loop()
    last_run = await loop.run_in_executor(None, _read_last_run)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(last_run, request_id)),
    )


# ─── GET /api/v1/scrape/rate-limits ──────────────────────────────────────────


def _get_rate_limit_status() -> dict:
    """Call RateLimiter.get_status() synchronously."""
    from agents.rate_limiter import RateLimiter
    return RateLimiter().get_status()


@router.get(
    "/rate-limits",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current API rate limit usage",
    description="Returns TinyFish and Amadeus daily call counts and limits.",
)
async def get_rate_limits(
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """GET /api/v1/scrape/rate-limits."""
    loop = asyncio.get_event_loop()
    rl_status = await loop.run_in_executor(None, _get_rate_limit_status)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(rl_status, request_id)),
    )
