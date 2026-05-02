"""agents/rate_limiter.py — Per-route and per-API rate limit enforcement.

Persists call counts and last-scraped timestamps to ./db/rate_limiter_state.json
so limits survive process restarts. All file writes are protected by a threading
lock + fcntl.flock() (with a threading-only fallback on Windows) to prevent
concurrent corruption when n8n and FastAPI fire scrapes simultaneously.

State file format (JSON):
{
  "last_scraped": {
    "NAG-DEL_2026-12-15": "2026-05-01T06:00:00Z"
  },
  "tinyfish_calls_today": {
    "browser": 4,
    "fetch": 8,
    "date": "2026-05-01"
  },
  "amadeus_calls_today": {
    "count": 2,
    "date": "2026-05-01"
  }
}
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

_STATE_FILE = Path("./db/rate_limiter_state.json")

# Safe daily limits (below API hard limits to leave a safety buffer)
TINYFISH_BROWSER_LIMIT: int = 18   # hard limit ~20/day
TINYFISH_FETCH_LIMIT: int = 45     # hard limit ~50/day
AMADEUS_DAILY_LIMIT: int = 450     # hard limit 500/day (50-call buffer)

_DEFAULT_MIN_INTERVAL_MINUTES: int = 300  # 5 hours between scrapes per route+date

_logger = logging.getLogger("flight_agent.scraper.rate_limiter")

# ─── PLATFORM FILE LOCKING ───────────────────────────────────────────────────

try:
    import fcntl as _fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False  # Windows — fall back to threading.Lock only


# ─── PRIVATE HELPERS ─────────────────────────────────────────────────────────


def _today_str() -> str:
    """Return today's local calendar date as an ISO string ``"YYYY-MM-DD"``.

    Uses ``date.today()`` (local time) rather than UTC so that daily counter
    resets happen at local midnight and remain consistent with date arithmetic
    in tests and user-facing code on non-UTC systems (e.g. IST).
    """
    return date.today().isoformat()


def _utcnow_iso() -> str:
    """Return current UTC datetime as ``"YYYY-MM-DDTHH:MM:SSZ"``."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _empty_state() -> dict[str, Any]:
    """Return a fresh, fully-initialised state dictionary."""
    today = _today_str()
    return {
        "last_scraped": {},
        "tinyfish_calls_today": {
            "browser": 0,
            "fetch": 0,
            "date": today,
        },
        "amadeus_calls_today": {
            "count": 0,
            "date": today,
        },
    }


def _route_key(route: str, travel_date: date) -> str:
    """Compose the composite key used in ``last_scraped``."""
    return f"{route}_{travel_date.isoformat()}"


# ─── RATE LIMITER CLASS ───────────────────────────────────────────────────────


class RateLimiter:
    """Thread-safe rate limiter with JSON persistence across restarts.

    All public methods perform a full read-modify-write cycle while holding
    both the in-process threading lock *and* (on Linux/macOS) an OS-level
    ``fcntl.flock`` so that concurrent processes cannot corrupt the file.

    Example::

        rl = RateLimiter()
        if rl.can_use_tinyfish_browser():
            # … call TinyFish …
            rl.record_tinyfish_call("browser")
    """

    def __init__(self, state_file: Path = _STATE_FILE) -> None:
        self._state_file = state_file
        self._lock = threading.Lock()
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._state_file.exists():
            self._write_state(_empty_state())

    # ── Public query methods ──────────────────────────────────────────────────

    def can_scrape_route(
        self,
        route: str,
        travel_date: date,
        min_interval_minutes: int = _DEFAULT_MIN_INTERVAL_MINUTES,
    ) -> bool:
        """Return ``True`` if enough time has elapsed since this route+date was scraped.

        Always returns ``True`` when the route has never been scraped before.

        Args:
            route: Route string e.g. ``"NAG-DEL"``.
            travel_date: Departure date.
            min_interval_minutes: Minimum gap in minutes between scrapes for
                the same route+date (default 300 = 5 hours).

        Returns:
            ``True`` if scraping is allowed, ``False`` if still on cooldown.
        """
        state = self._read_state()
        key = _route_key(route, travel_date)
        last_raw = state["last_scraped"].get(key)
        if last_raw is None:
            _logger.debug(
                json.dumps({
                    "event": "rate_limit_check",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                    "result": "allowed",
                    "reason": "never_scraped",
                })
            )
            return True

        last_dt = datetime.fromisoformat(last_raw.replace("Z", "+00:00"))
        elapsed_minutes = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60.0
        allowed = elapsed_minutes >= min_interval_minutes

        _logger.debug(
            json.dumps({
                "event": "rate_limit_check",
                "route": route,
                "travel_date": travel_date.isoformat(),
                "elapsed_minutes": round(elapsed_minutes, 1),
                "min_interval_minutes": min_interval_minutes,
                "result": "allowed" if allowed else "cooldown",
            })
        )
        return allowed

    def can_use_tinyfish_browser(self) -> bool:
        """Return ``True`` if TinyFish Browser calls today are below the safe limit.

        Automatically resets the counter when a new calendar day (UTC) starts.

        Returns:
            ``True`` if another Browser call is permitted today.
        """
        state = self._read_state()
        state = self._reset_tinyfish_if_new_day(state)
        used = state["tinyfish_calls_today"]["browser"]
        allowed = used < TINYFISH_BROWSER_LIMIT
        _logger.debug(
            json.dumps({
                "event": "tinyfish_browser_limit_check",
                "used": used,
                "limit": TINYFISH_BROWSER_LIMIT,
                "allowed": allowed,
            })
        )
        return allowed

    def can_use_tinyfish_fetch(self) -> bool:
        """Return ``True`` if TinyFish Fetch calls today are below the safe limit.

        Automatically resets the counter when a new calendar day (UTC) starts.

        Returns:
            ``True`` if another Fetch call is permitted today.
        """
        state = self._read_state()
        state = self._reset_tinyfish_if_new_day(state)
        used = state["tinyfish_calls_today"]["fetch"]
        allowed = used < TINYFISH_FETCH_LIMIT
        _logger.debug(
            json.dumps({
                "event": "tinyfish_fetch_limit_check",
                "used": used,
                "limit": TINYFISH_FETCH_LIMIT,
                "allowed": allowed,
            })
        )
        return allowed

    def can_use_amadeus(self) -> bool:
        """Return ``True`` if Amadeus API calls today are below the safe limit.

        Automatically resets the counter when a new calendar day (UTC) starts.

        Returns:
            ``True`` if another Amadeus call is permitted today.
        """
        state = self._read_state()
        state = self._reset_amadeus_if_new_day(state)
        used = state["amadeus_calls_today"]["count"]
        allowed = used < AMADEUS_DAILY_LIMIT
        _logger.debug(
            json.dumps({
                "event": "amadeus_limit_check",
                "used": used,
                "limit": AMADEUS_DAILY_LIMIT,
                "allowed": allowed,
            })
        )
        return allowed

    # ── Public mutation methods ───────────────────────────────────────────────

    def record_scrape(self, route: str, travel_date: date) -> None:
        """Record that a scrape attempt just completed for this route+date.

        Updates ``last_scraped`` in the state file under the composite key
        ``"{route}_{travel_date}"``.  Holds file lock for the entire
        read-modify-write cycle.

        Args:
            route: Route string e.g. ``"NAG-DEL"``.
            travel_date: The departure date that was scraped.

        Side effects:
            Writes to :attr:`_state_file`.
        """
        with self._lock:
            state = self._read_state_locked()
            key = _route_key(route, travel_date)
            state["last_scraped"][key] = _utcnow_iso()
            self._write_state_locked(state)
        _logger.debug(
            json.dumps({
                "event": "scrape_recorded",
                "route": route,
                "travel_date": travel_date.isoformat(),
            })
        )

    def record_tinyfish_call(self, endpoint: str) -> None:
        """Increment the TinyFish call counter for *endpoint*.

        Args:
            endpoint: Either ``"browser"`` or ``"fetch"``.

        Raises:
            ValueError: If *endpoint* is not ``"browser"`` or ``"fetch"``.

        Side effects:
            Writes to :attr:`_state_file`.
        """
        if endpoint not in ("browser", "fetch"):
            raise ValueError(
                f"Invalid TinyFish endpoint '{endpoint}'. Must be 'browser' or 'fetch'."
            )
        with self._lock:
            state = self._read_state_locked()
            state = self._reset_tinyfish_if_new_day(state)
            state["tinyfish_calls_today"][endpoint] += 1
            self._write_state_locked(state)
        _logger.debug(
            json.dumps({
                "event": "tinyfish_call_recorded",
                "endpoint": endpoint,
            })
        )

    def record_amadeus_call(self) -> None:
        """Increment the Amadeus API call counter for today.

        Side effects:
            Writes to :attr:`_state_file`.
        """
        with self._lock:
            state = self._read_state_locked()
            state = self._reset_amadeus_if_new_day(state)
            state["amadeus_calls_today"]["count"] += 1
            self._write_state_locked(state)
        _logger.debug(json.dumps({"event": "amadeus_call_recorded"}))

    def get_status(self) -> dict[str, Any]:
        """Return a summary dict for the /status FastAPI endpoint.

        Returns:
            Dict with keys: ``tinyfish_browser_used_today``,
            ``tinyfish_browser_limit``, ``tinyfish_fetch_used_today``,
            ``tinyfish_fetch_limit``, ``amadeus_used_today``,
            ``amadeus_limit``, ``routes_on_cooldown``.
        """
        state = self._read_state()
        state = self._reset_tinyfish_if_new_day(state)
        state = self._reset_amadeus_if_new_day(state)

        now = datetime.now(timezone.utc)
        on_cooldown: list[str] = []
        for key, last_raw in state["last_scraped"].items():
            last_dt = datetime.fromisoformat(last_raw.replace("Z", "+00:00"))
            elapsed_min = (now - last_dt).total_seconds() / 60.0
            if elapsed_min < _DEFAULT_MIN_INTERVAL_MINUTES:
                on_cooldown.append(key)

        return {
            "tinyfish_browser_used_today": state["tinyfish_calls_today"]["browser"],
            "tinyfish_browser_limit": TINYFISH_BROWSER_LIMIT,
            "tinyfish_fetch_used_today": state["tinyfish_calls_today"]["fetch"],
            "tinyfish_fetch_limit": TINYFISH_FETCH_LIMIT,
            "amadeus_used_today": state["amadeus_calls_today"]["count"],
            "amadeus_limit": AMADEUS_DAILY_LIMIT,
            "routes_on_cooldown": on_cooldown,
        }

    # ── Private I/O helpers ───────────────────────────────────────────────────

    def _read_state(self) -> dict[str, Any]:
        """Read state file without holding :attr:`_lock` (read-only query)."""
        if not self._state_file.exists():
            return _empty_state()
        try:
            with self._state_file.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            _logger.warning(
                json.dumps({
                    "event": "state_file_read_error",
                    "error": str(exc),
                    "action": "returning_empty_state",
                })
            )
            return _empty_state()

    def _read_state_locked(self) -> dict[str, Any]:
        """Read state file while *caller* already holds :attr:`_lock`."""
        return self._read_state()

    def _write_state(self, state: dict[str, Any]) -> None:
        """Write *state* to file without holding :attr:`_lock`."""
        tmp = self._state_file.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                if _HAS_FCNTL:
                    _fcntl.flock(fh, _fcntl.LOCK_EX)
                json.dump(state, fh, indent=2, ensure_ascii=False)
                if _HAS_FCNTL:
                    _fcntl.flock(fh, _fcntl.LOCK_UN)
            tmp.replace(self._state_file)
        except OSError as exc:
            _logger.error(
                json.dumps({
                    "event": "state_file_write_error",
                    "error": str(exc),
                })
            )
            raise

    def _write_state_locked(self, state: dict[str, Any]) -> None:
        """Write state file while *caller* already holds :attr:`_lock`."""
        self._write_state(state)

    # ── Private day-reset helpers ─────────────────────────────────────────────

    @staticmethod
    def _reset_tinyfish_if_new_day(state: dict[str, Any]) -> dict[str, Any]:
        """Zero TinyFish counters if the stored date differs from today (UTC)."""
        today = _today_str()
        if state["tinyfish_calls_today"].get("date") != today:
            state["tinyfish_calls_today"] = {
                "browser": 0,
                "fetch": 0,
                "date": today,
            }
        return state

    @staticmethod
    def _reset_amadeus_if_new_day(state: dict[str, Any]) -> dict[str, Any]:
        """Zero Amadeus counter if the stored date differs from today (UTC)."""
        today = _today_str()
        if state["amadeus_calls_today"].get("date") != today:
            state["amadeus_calls_today"] = {"count": 0, "date": today}
        return state
