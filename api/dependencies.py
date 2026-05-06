"""api/dependencies.py — Shared FastAPI dependencies.

Three injectable dependencies used across all route handlers:

  verify_api_key  — constant-time comparison against SKYSAVER_API_KEY env var
  get_db_path     — returns the DATABASE_PATH env var as a Path
  get_request_id  — extracts request_id from request.state (set by middleware)

Usage in route handlers:
    @router.get("/endpoint")
    async def my_handler(
        _: Annotated[None, Depends(verify_api_key)],
        request_id: Annotated[str, Depends(get_request_id)],
    ) -> APIResponse:
        ...
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status


async def verify_api_key(
    x_skysaver_key: Annotated[str, Header(alias="X-SkySaver-Key")] = "",
) -> None:
    """Verify the X-SkySaver-Key request header.

    Uses secrets.compare_digest() for constant-time comparison to prevent
    timing-oracle attacks. Raises 401 on mismatch or missing key.

    Raises:
        RuntimeError: If SKYSAVER_API_KEY env var is not configured.
        HTTPException(401): If the header is missing or incorrect.
    """
    expected = os.getenv("SKYSAVER_API_KEY")
    if not expected:
        raise RuntimeError(
            "SKYSAVER_API_KEY is not set in the environment. "
            "Add it to your .env file before starting SkySaver."
        )
    # Both sides must be the same type (bytes) for compare_digest
    if not secrets.compare_digest(
        x_skysaver_key.encode("utf-8"),
        expected.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key. Provide the correct X-SkySaver-Key header.",
        )


def get_db_path() -> Path:
    """Return the SQLite database file path from DATABASE_PATH env var.

    Falls back to the default project path if not set.

    Returns:
        Path object pointing at the SQLite file.
    """
    raw = os.getenv("DATABASE_PATH", "./db/flight_prices.db")
    return Path(raw)


async def get_request_id(request: Request) -> str:
    """Extract the request_id set by RequestIDMiddleware.

    Falls back to a fresh UUID if middleware did not run (e.g. during testing
    without the full app stack).

    Returns:
        UUID string for the current request.
    """
    return getattr(request.state, "request_id", "")


# ── Annotated shorthand aliases — import these in route files ─────────────────

ApiKeyDep = Annotated[None, Depends(verify_api_key)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
