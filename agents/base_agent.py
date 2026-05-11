"""agents/base_agent.py — Shared base utilities for all SkySaver agents.

Provides: LLM config factories, structured JSON logger, environment validator,
timing decorator, and UTC datetime helpers. Intentionally has ZERO imports from
ag2/tinyfish/skyscrapper so this module can be imported without those packages.
"""

# ─── GEMINI MODEL STRATEGY FOR THIS PROJECT ────────────────────────────────────
#
# ALL LLM usage in this project goes through a single GEMINI_API_KEY.
# Two functions are provided and each serves a distinct role:
#
#   get_gemini_flash_config()
#   Model:  gemini-2.5-flash
#   Cost:   $0.30 / $2.50 per 1M tokens
#   Use:    ScraperAgent — TinyFish response parsing, fare extraction from HTML,
#           airline name normalisation, price string cleanup. Thinking DISABLED
#           (thinking_budget=0) for maximum speed and minimum cost.
#
#   get_gemini_pro_config()
#   Model:  gemini-2.5-pro
#   Cost:   $1.25 / $10.00 per 1M tokens (≤200K context)
#   Use:    AnalyzerAgent (Phase 3) — price trend reasoning, all-time cheapest
#           determination, multi-route comparison, booking recommendation.
#           Thinking AUTOMATIC (thinking_budget=-1) for quality reasoning.
#
# Estimated monthly cost for personal use (single user, ~4 routes, 6h scrape cycle):
#   Flash (scraping):  ~4 routes × 4 calls/day × 30 days × ~500 tokens = ~240K tokens → <$0.10/mo
#   Pro (analysis):    ~4 routes × 4 decisions/day × 30 days × ~2K tokens = ~960K tokens → ~$1.20/mo
#   Total LLM cost:    < $1.50/month
#
# ────────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import functools
import json
import logging
import os
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

# ─── TYPE VARS ───────────────────────────────────────────────────────────────

_F = TypeVar("_F", bound=Callable[..., Any])

# ─── REQUIRED ENVIRONMENT VARIABLES ─────────────────────────────────────────

_REQUIRED_ENV_VARS: tuple[str, ...] = (
    "GEMINI_API_KEY",          # single key for ALL LLM purposes (Flash + Pro)
    "TINYFISH_API_KEY",
    "RAPIDAPI_KEY",            # Sky Scrapper API via RapidAPI (Tier 3 fallback)
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "DATABASE_PATH",
    "SKYSAVER_API_KEY",        # API authentication key for the FastAPI layer
)

# ─── LOG FORMAT ──────────────────────────────────────────────────────────────

_LOG_DIR = Path("./logs")
_LOG_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
_LOG_BACKUP_COUNT = 5

# ─── PRIVATE: JSON LOG FORMATTER ─────────────────────────────────────────────


class _JsonFormatter(logging.Formatter):
    """Emit every log record as a single-line JSON object.

    Fields included: timestamp (ISO-8601 UTC), level, logger, message.
    If the message is already valid JSON, it is embedded directly as
    the ``payload`` field rather than double-encoded.
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        msg = record.getMessage()
        try:
            payload = json.loads(msg)
        except (json.JSONDecodeError, TypeError):
            payload = msg

        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "payload": payload,
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


# ─── PUBLIC: LOGGER FACTORY ───────────────────────────────────────────────────


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """Return a configured logger with JSON formatter.

    Idempotent — calling this twice with the same *name* returns the same
    logger without adding duplicate handlers.

    Args:
        name: Dotted logger name, e.g. ``"flight_agent.scraper.tinyfish"``.
        log_file: Optional filename (relative to ``./logs/``). When provided,
            a ``RotatingFileHandler`` is added (max 50 MB × 5 backups).

    Returns:
        Fully configured :class:`logging.Logger` instance.

    Side effects:
        Creates ``./logs/`` directory if *log_file* is provided and the
        directory does not exist.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls (e.g. during tests).
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = _JsonFormatter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)

    if log_file is not None:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_path = _LOG_DIR / log_file
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=_LOG_MAX_BYTES,
            backupCount=_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    # Prevent log records from propagating to the root logger's plain handler.
    logger.propagate = False
    return logger


# ─── PUBLIC: ENVIRONMENT LOADER ──────────────────────────────────────────────


def load_env() -> None:
    """
    Load .env file and validate all required environment variables are present.

    Google Gemini API key (GEMINI_API_KEY) covers ALL LLM tasks in this project:
      - Gemini 2.5 Flash: scraping agent, fare parsing, TinyFish result extraction
      - Gemini 2.5 Pro:   analyzer agent, price reasoning, booking recommendations

    A single paid Gemini API key is sufficient for the entire system.
    Get your key at: https://aistudio.google.com/app/apikey

    Raises:
        RuntimeError: If any required variable is missing. Lists ALL missing
                      variables in one error so the user can fix them all at once.
    """
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]

        load_dotenv(override=False)
    except ImportError:
        pass  # python-dotenv not installed; rely on actual env

    missing = [k for k in _REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "SkySaver startup failed — missing required environment variables:\n"
            + "\n".join(f"  • {k}" for k in missing)
            + "\nSet them in your .env file or export them before starting."
        )


# ─── PUBLIC: LLM CONFIG FACTORIES ───────────────────────────────────────────


def get_gemini_flash_config() -> dict:
    """
    Return AG2 config dict for Gemini 2.5 Flash.

    Use for: TinyFish response parsing, HTML fare extraction, bulk pattern matching.
    Thinking is DISABLED (thinking_budget=0) — Flash is used for speed and cost,
    not deep reasoning. At $0.30/$2.50 per 1M tokens, this is the cheapest
    production-quality option for structured extraction tasks.

    Returns a plain dict — compatible with ag2>=0.3 which dropped LLMConfig().

    Side effects: None.
    Raises: RuntimeError if GEMINI_API_KEY is not set in environment.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Get your key from https://aistudio.google.com/app/apikey"
        )

    return {
        "model": "gemini-2.5-flash",
        "api_type": "google",
        "api_key": api_key,
        "thinking_budget": 0,        # DISABLED — speed over reasoning for parsing
    }


def get_gemini_pro_config() -> dict:
    """
    Return AG2 LLMConfig for Gemini 2.5 Pro with automatic thinking enabled.

    Use for: AnalyzerAgent (Phase 3) — price trend reasoning, all-time cheapest
    determination, booking recommendation generation. This is the direct
    replacement for deep-reasoning tasks in Phase 3.

    thinking_budget=-1 means AUTOMATIC: Gemini dynamically allocates thinking
    tokens based on task complexity. Simple comparisons use few tokens; complex
    multi-route analysis uses more. This is the recommended setting for
    reasoning-heavy tasks where token usage is unpredictable.

    At $1.25/$10.00 per 1M tokens (≤200K context), Pro reasoning costs remain
    low for this use case — the AnalyzerAgent processes short price summaries,
    not long documents.

    Side effects: None.
    Raises: RuntimeError if GEMINI_API_KEY is not set in environment.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Get your key from https://aistudio.google.com/app/apikey"
        )

    return {
        "model": "gemini-2.5-pro",
        "api_type": "google",
        "api_key": api_key,
        "thinking_budget": -1,       # AUTOMATIC — model decides thinking depth
        "include_thoughts": False,   # Do not include thought summaries in response
                                     # (cleaner output for structured JSON responses)
    }


# ─── PUBLIC: TIMING DECORATOR ─────────────────────────────────────────────────


def timed(func: _F) -> _F:
    """Decorator that measures wall-clock execution time of *func*.

    Wraps the decorated function so that instead of returning ``result``,
    it returns ``(result, duration_seconds: float)``.

    Example::

        @timed
        def fetch_data() -> list[str]:
            ...

        data, elapsed = fetch_data()
        print(f"Fetched {len(data)} items in {elapsed:.2f}s")

    Args:
        func: Any callable to wrap.

    Returns:
        Wrapped callable with the same signature but a 2-tuple return value.
    """

    @functools.wraps(func)
    def _wrapper(*args: Any, **kwargs: Any) -> tuple[Any, float]:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        return result, elapsed

    return _wrapper  # type: ignore[return-value]


# ─── PUBLIC: UTC HELPERS ──────────────────────────────────────────────────────


def utcnow() -> datetime:
    """Return the current UTC datetime as a timezone-aware object.

    Always use this instead of ``datetime.utcnow()`` (deprecated in 3.12+).

    Returns:
        :class:`datetime` with ``tzinfo=timezone.utc``.
    """
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    """Convert a datetime to a compact ISO-8601 UTC string.

    Example::

        to_iso(utcnow())  # "2026-05-01T06:00:00Z"

    Args:
        dt: Any :class:`datetime`. If naïve, it is assumed to be UTC.

    Returns:
        ISO-8601 string with seconds precision, always ending in ``"Z"``.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
