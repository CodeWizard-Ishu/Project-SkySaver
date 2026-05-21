"""api/routes/scrape.py — Scraping trigger and status endpoints.

Endpoints:
  POST /api/v1/scrape/run              — Trigger a full pipeline run (non-blocking, returns 202)
  GET  /api/v1/scrape/job/{job_id}     — Poll job status and result
  GET  /api/v1/scrape/running          — Check if a pipeline job is currently active
  GET  /api/v1/scrape/last-run         — Return summary of last pipeline run
  GET  /api/v1/scrape/rate-limits      — Return current API rate limit usage

Design: /run fires the pipeline in a daemon thread and returns immediately.
The caller polls /job/{job_id} until status is 'done' or 'error'.

Job Persistence: all job state is written atomically to db/jobs.json so that
  n8n can continue polling even after a uvicorn reload or Gunicorn restart.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
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
_JOBS_PATH = Path("db/jobs.json")  # persistent job registry

# ─── Persistent Job Registry ───────────────────────────────────────────────────
# Jobs are kept in memory for fast reads, and flushed to disk on every write
# so they survive uvicorn --reload and Gunicorn worker restarts.

_jobs_lock = threading.Lock()


def _load_jobs_from_disk() -> dict[str, dict]:
    """Load existing jobs from db/jobs.json on startup."""
    if not _JOBS_PATH.exists():
        return {}
    try:
        raw = json.loads(_JOBS_PATH.read_text(encoding="utf-8"))
        _log.info('{"event":"jobs_loaded_from_disk","count":%d}', len(raw))
        return raw
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning('{"event":"jobs_load_error","error":"%s"}', exc)
        return {}


def _persist_jobs(jobs: dict[str, dict]) -> None:
    """Atomically write the full jobs dict to db/jobs.json.

    Uses a tmp file + os.replace() for atomic write — safe even if the
    process is killed mid-write.
    """
    _JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _JOBS_PATH.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(jobs, default=str), encoding="utf-8")
        os.replace(tmp, _JOBS_PATH)
    except OSError as exc:
        _log.error('{"event":"jobs_persist_error","error":"%s"}', exc)
        tmp.unlink(missing_ok=True)


# Load jobs on module import (covers uvicorn --reload restarts).
# Any job left in 'running' state from a previous process is now orphaned —
# its thread died with the old process. Mark it as error so n8n stops polling.
def _load_and_fix_jobs() -> dict[str, dict]:
    jobs = _load_jobs_from_disk()
    orphans = [jid for jid, j in jobs.items() if j.get("status") == "running"]
    if orphans:
        for jid in orphans:
            jobs[jid]["status"] = "error"
            jobs[jid]["error"] = "Server restarted while job was running."
            jobs[jid]["finished_at"] = time.time()
        _persist_jobs(jobs)
        _log.warning('{\"event\":\"orphaned_jobs_fixed\",\"count\":%d}', len(orphans))
    return jobs


_jobs: dict[str, dict] = _load_and_fix_jobs()

# Single shared executor — limits concurrency to 1 pipeline at a time
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")


# ─── POST /api/v1/scrape/run ─────────────────────────────────────────────────


def _run_pipeline_sync(dry_run: bool = False) -> ScrapeRunResponse:
    """Execute the full pipeline synchronously (runs in thread pool)."""
    from agents.pipeline import PipelineRunner
    import time as _time

    t_start = _time.perf_counter()
    runner = PipelineRunner()
    result = runner.run()
    duration = round(_time.perf_counter() - t_start, 2)

    sr = result.scrape_result
    alerts_sent = result.alerts_sent if not dry_run else 0

    return ScrapeRunResponse(
        routes_attempted=sr.routes_attempted,
        routes_succeeded=sr.routes_succeeded,
        routes_failed=sr.routes_failed,
        total_fares_scraped=sr.total_fares_scraped,
        alerts_sent=alerts_sent,
        retrain_triggered=result.retrain_triggered,
        duration_seconds=duration,
        errors=list(result.errors),
    )


def _pipeline_worker(job_id: str, dry_run: bool) -> None:
    """Worker function that runs in a thread pool thread."""
    try:
        result = _run_pipeline_sync(dry_run)
        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = result.model_dump()
            _jobs[job_id]["finished_at"] = time.time()
            _persist_jobs(_jobs)  # survive restarts
    except Exception as exc:
        _log.error('{"event":"pipeline_worker_error","job_id":"%s","error":"%s"}',
                   job_id, str(exc))
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(exc)
            _jobs[job_id]["finished_at"] = time.time()
            _persist_jobs(_jobs)  # survive restarts


@router.post(
    "/run",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a full pipeline run (non-blocking)",
    description=(
        "Starts a pipeline run in the background and returns immediately with a job_id. "
        "Poll GET /scrape/job/{job_id} to check status and retrieve results. "
        "Returns 409 if a pipeline job is already running."
    ),
)
async def trigger_scrape_run(
    _: ApiKeyDep,
    request_id: RequestIdDep,
    body: Optional[ScrapeRunRequest] = None,
) -> JSONResponse:
    """POST /api/v1/scrape/run — fire-and-forget pipeline trigger."""
    dry_run = body.dry_run if body else False

    # Reject concurrent pipeline runs
    with _jobs_lock:
        running = [j for j in _jobs.values() if j["status"] == "running"]
        if running:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=jsonable_encoder(error_response(
                    "A pipeline run is already in progress. "
                    f"Poll /scrape/job/{running[0]['job_id']} for status.",
                    request_id,
                )),
            )

        job_id = str(uuid.uuid4())[:8]
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "dry_run": dry_run,
            "started_at": time.time(),
            "result": None,
            "error": None,
        }
        _persist_jobs(_jobs)  # write immediately so restart-poll finds the job

    _log.info('{"event":"pipeline_job_started","job_id":"%s","dry_run":%s}',
               job_id, str(dry_run).lower())
    _executor.submit(_pipeline_worker, job_id, dry_run)

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=jsonable_encoder(success_response(
            {"job_id": job_id, "status": "running",
             "poll_url": f"/api/v1/scrape/job/{job_id}"},
            request_id,
        )),
    )


# ─── GET /api/v1/scrape/job/{job_id} ────────────────────────────────────────


@router.get(
    "/job/{job_id}",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Poll pipeline job status",
    description="Returns status ('running'|'done'|'error') and result once complete.",
)
async def get_job_status(
    job_id: str,
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """GET /api/v1/scrape/job/{job_id} — poll job completion."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    payload = {
        "job_id": job["job_id"],
        "status": job["status"],
        "started_at": job["started_at"],
        "finished_at": job.get("finished_at"),
        "elapsed_seconds": round(time.time() - job["started_at"], 1),
        "result": job.get("result"),
        "error": job.get("error"),
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(payload, request_id)),
    )


# ─── GET /api/v1/scrape/running ──────────────────────────────────────────────


@router.get(
    "/running",
    response_model=APIResponse,
    status_code=status.HTTP_200_OK,
    summary="Check if a pipeline is currently running",
)
async def get_running_status(
    _: ApiKeyDep,
    request_id: RequestIdDep,
) -> JSONResponse:
    """GET /api/v1/scrape/running — returns active job info if any."""
    with _jobs_lock:
        running = [j for j in _jobs.values() if j["status"] == "running"]
    payload = {
        "is_running": bool(running),
        "job": running[0] if running else None,
    }
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(payload, request_id)),
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
    loop = asyncio.get_running_loop()
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
    loop = asyncio.get_running_loop()
    rl_status = await loop.run_in_executor(None, _get_rate_limit_status)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=jsonable_encoder(success_response(rl_status, request_id)),
    )
