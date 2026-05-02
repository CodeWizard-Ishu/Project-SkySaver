"""db/queries.py — Complete read/write API for SkySaver flight price database.

This is the ONLY file in the project that touches SQLite directly. All other
modules (scraper, analyzer, ML engine, alert system) import from here.
Thread-safe via WAL mode + a module-level write lock. Returns typed dataclasses.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

import os

logger = logging.getLogger("flight_agent.db")

_VALID_SOURCES = frozenset({"skyscanner", "google_flights", "amadeus"})
_ROUTE_RE = re.compile(r"^[A-Z]{2,4}-[A-Z]{2,4}$")

# ─── EXCEPTIONS ─────────────────────────────────────────────────────────────

class DatabaseError(Exception):
    """Base exception for all database layer errors."""

class RouteNotFoundError(DatabaseError):
    """Raised when querying a route not in monitored_routes."""

class InsufficientDataError(DatabaseError):
    """Raised when a route has fewer observations than the minimum required."""

class AlertCooldownError(DatabaseError):
    """Raised when an alert was already sent within the cooldown period."""

# ─── DATACLASSES ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PriceObservation:
    id: int
    observed_at: datetime
    route: str
    travel_date: date
    price_inr: int
    airline: str
    stops: int
    days_advance: int
    source: str

@dataclass(frozen=True)
class PriceStats:
    route: str
    travel_date: date
    p10_price: Optional[int]
    p25_price: Optional[int]
    median_price: Optional[int]
    all_time_low: Optional[int]
    all_time_high: Optional[int]
    observation_count: int
    last_updated: datetime

@dataclass(frozen=True)
class AlertDecision:
    should_alert: bool
    current_price: int
    reason: str
    percentile_rank: Optional[float]
    pct_below_median: Optional[float]
    p10_price: Optional[int]
    all_time_low: Optional[int]
    observation_count: int

@dataclass(frozen=True)
class MLForecast:
    route: str
    travel_date: date
    forecast_7d_price: Optional[int]
    forecast_direction: Optional[str]
    lgbm_score: Optional[float]
    confidence: Optional[float]
    model_version: str
    created_at: datetime

# ─── CONNECTION MANAGEMENT ───────────────────────────────────────────────────

_conn: Optional[sqlite3.Connection] = None
_write_lock = threading.Lock()


def _get_db_path() -> str:
    return os.environ.get("DATABASE_PATH", "./db/flight_prices.db")


def get_connection() -> sqlite3.Connection:
    """Return the module-level thread-safe SQLite connection (lazy init).

    Applies all production PRAGMAs on first call. WAL mode enables concurrent
    reads from multiple threads while a single writer holds the lock.

    Returns:
        Configured sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    global _conn
    if _conn is not None:
        return _conn

    db_path = Path(_get_db_path())
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    _conn.row_factory = sqlite3.Row

    pragmas = [
        "PRAGMA journal_mode = WAL",
        "PRAGMA synchronous = NORMAL",
        "PRAGMA busy_timeout = 5000",
        "PRAGMA foreign_keys = ON",
        "PRAGMA cache_size = -64000",
        "PRAGMA temp_store = MEMORY",
        "PRAGMA mmap_size = 268435456",
    ]
    for pragma in pragmas:
        _conn.execute(pragma)
    _conn.commit()

    logger.info('{"level":"INFO","event":"db_connected","path":"%s"}', db_path)
    return _conn


def close_connection() -> None:
    """Cleanly close the database connection. Safe to call if never opened.

    Called by FastAPI shutdown event and main.py cleanup.
    """
    global _conn
    if _conn is not None:
        try:
            _conn.close()
            logger.info('{"level":"INFO","event":"db_closed"}')
        except sqlite3.Error as exc:
            logger.error('{"level":"ERROR","event":"db_close_failed","error":"%s"}', exc)
        finally:
            _conn = None

# ─── PRIVATE HELPERS ─────────────────────────────────────────────────────────

def _validate_route_format(route: str) -> None:
    if not _ROUTE_RE.match(route):
        raise ValueError(
            f"Invalid route format: '{route}'. "
            "Expected uppercase IATA codes separated by hyphen, e.g. 'NAG-DEL'."
        )


def _percentile_nearest_rank(sorted_prices: list[int], pct: float) -> int:
    """Nearest-rank percentile on a sorted ascending list."""
    n = len(sorted_prices)
    idx = max(0, int(pct / 100.0 * n) - 1) if pct > 0 else 0
    idx = min(idx, n - 1)
    return sorted_prices[idx]


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

# ─── WRITE OPERATIONS ────────────────────────────────────────────────────────

def insert_price_observation(
    route: str,
    travel_date: date,
    price_inr: int,
    airline: str,
    stops: int,
    source: str,
) -> int:
    """Insert one scraped price observation into flight_prices.

    Calculates days_advance automatically. Sets observed_at to current UTC.
    Validates route format, source, and price before touching the DB.

    Args:
        route: e.g. "NAG-DEL"
        travel_date: Departure date.
        price_inr: Fare in INR (must be > 0).
        airline: Airline name e.g. "IndiGo".
        stops: Number of stops (0 = non-stop).
        source: One of skyscanner | google_flights | amadeus.

    Returns:
        Auto-generated row ID of the inserted observation.

    Raises:
        ValueError: If route, price, or source fails validation.
        DatabaseError: If the SQL insert fails.
    """
    _validate_route_format(route)
    if price_inr <= 0:
        raise ValueError(f"price_inr must be > 0, got {price_inr}.")
    if source not in _VALID_SOURCES:
        raise ValueError(f"Invalid source '{source}'. Must be one of {sorted(_VALID_SOURCES)}.")
    if stops < 0:
        raise ValueError(f"stops must be >= 0, got {stops}.")

    observed_at = _now_utc_iso()
    today = datetime.now(UTC).date()
    days_advance = (travel_date - today).days
    if days_advance < 0:
        days_advance = 0

    sql = """
        INSERT INTO flight_prices
            (observed_at, route, travel_date, price_inr, airline, stops, days_advance, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        observed_at, route, travel_date.isoformat(),
        price_inr, airline, stops, days_advance, source,
    )

    try:
        with _write_lock:
            conn = get_connection()
            with conn:
                cur = conn.execute(sql, params)
                row_id = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise DatabaseError(f"Integrity error inserting observation: {exc}") from exc
    except sqlite3.OperationalError as exc:
        raise DatabaseError(f"Operational error inserting observation: {exc}") from exc

    logger.info(
        '{"level":"INFO","event":"price_inserted","route":"%s","travel_date":"%s","price":%d}',
        route, travel_date.isoformat(), price_inr,
    )
    return row_id


def update_price_stats(route: str, travel_date: date) -> PriceStats:
    """Recalculate and upsert price_stats for a route+date pair.

    Reads ALL observations from flight_prices, computes P10/P25/median/
    all-time low/high, then upserts into price_stats.

    Args:
        route: Route string e.g. "NAG-DEL".
        travel_date: Travel date to recalculate.

    Returns:
        PriceStats dataclass with freshly computed values.

    Raises:
        InsufficientDataError: If zero observations exist.
        DatabaseError: If any DB operation fails.
    """
    _validate_route_format(route)
    conn = get_connection()

    rows = conn.execute(
        "SELECT price_inr FROM flight_prices WHERE route=? AND travel_date=? ORDER BY price_inr ASC",
        (route, travel_date.isoformat()),
    ).fetchall()

    if not rows:
        raise InsufficientDataError(
            f"No observations for route='{route}' travel_date='{travel_date}'. "
            "Cannot compute stats."
        )

    prices = sorted(int(r["price_inr"]) for r in rows)
    n = len(prices)

    p10 = _percentile_nearest_rank(prices, 10)
    p25 = _percentile_nearest_rank(prices, 25)
    median = _percentile_nearest_rank(prices, 50)
    atl = prices[0]
    ath = prices[-1]
    now_iso = _now_utc_iso()

    sql = """
        INSERT OR REPLACE INTO price_stats
            (route, travel_date, p10_price, p25_price, median_price,
             all_time_low, all_time_high, observation_count, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        with _write_lock:
            with conn:
                conn.execute(sql, (
                    route, travel_date.isoformat(),
                    p10, p25, median, atl, ath, n, now_iso,
                ))
    except sqlite3.OperationalError as exc:
        raise DatabaseError(f"Failed to upsert price_stats: {exc}") from exc

    logger.info(
        '{"level":"INFO","event":"stats_updated","route":"%s","travel_date":"%s","n":%d}',
        route, travel_date.isoformat(), n,
    )
    return PriceStats(
        route=route, travel_date=travel_date,
        p10_price=p10, p25_price=p25, median_price=median,
        all_time_low=atl, all_time_high=ath,
        observation_count=n,
        last_updated=datetime.fromisoformat(now_iso.replace("Z", "+00:00")),
    )


def store_ml_forecast(
    route: str,
    travel_date: date,
    forecast_7d_price: Optional[int],
    forecast_direction: Optional[str],
    lgbm_score: Optional[float],
    confidence: Optional[float],
    model_version: str,
) -> int:
    """Store one ML model prediction. Append-only — never updates existing rows.

    Args:
        route: Route string.
        travel_date: Travel date this forecast covers.
        forecast_7d_price: LSTM predicted price in 7 days (INR).
        forecast_direction: "up" | "down" | "flat" | None.
        lgbm_score: LightGBM cheapness probability 0–1.
        confidence: Overall model confidence 0–1.
        model_version: e.g. "lgbm_v1_2026-06-01".

    Returns:
        Row ID of the inserted forecast.

    Raises:
        DatabaseError: If the insert fails.
    """
    _validate_route_format(route)
    sql = """
        INSERT INTO ml_forecasts
            (route, travel_date, forecast_7d_price, forecast_direction,
             lgbm_score, confidence, model_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        with _write_lock:
            conn = get_connection()
            with conn:
                cur = conn.execute(sql, (
                    route, travel_date.isoformat(),
                    forecast_7d_price, forecast_direction,
                    lgbm_score, confidence, model_version, _now_utc_iso(),
                ))
                return cur.lastrowid
    except sqlite3.OperationalError as exc:
        raise DatabaseError(f"Failed to store ML forecast: {exc}") from exc


def log_alert_sent(
    route: str,
    travel_date: date,
    price_notified: int,
    alert_reason: str,
) -> int:
    """Record that a Telegram alert was sent. Sets alerted_at to current UTC.

    Args:
        route: Route string.
        travel_date: Travel date the alert was about.
        price_notified: Price that triggered the alert.
        alert_reason: Human-readable reason for the alert.

    Returns:
        Row ID of the inserted alert log entry.

    Raises:
        DatabaseError: If the insert fails.
    """
    _validate_route_format(route)
    sql = """
        INSERT INTO alert_log (route, travel_date, price_notified, alert_reason, alerted_at)
        VALUES (?, ?, ?, ?, ?)
    """
    try:
        with _write_lock:
            conn = get_connection()
            with conn:
                cur = conn.execute(sql, (
                    route, travel_date.isoformat(),
                    price_notified, alert_reason, _now_utc_iso(),
                ))
                return cur.lastrowid
    except sqlite3.OperationalError as exc:
        raise DatabaseError(f"Failed to log alert: {exc}") from exc


def upsert_monitored_route(
    route: str,
    travel_dates: list[str],
    check_every_hours: int = 6,
    active: bool = True,
) -> None:
    """Insert or update a route in monitored_routes registry.

    Sets created_at on first insert; updates updated_at on every call.
    travel_dates is stored as a JSON array string.

    Args:
        route: Route string e.g. "NAG-DEL".
        travel_dates: List of ISO date strings e.g. ["2026-12-15"].
        check_every_hours: Scrape interval in hours.
        active: Whether the route is actively monitored.

    Raises:
        ValueError: If route format invalid or travel_dates is empty.
    """
    _validate_route_format(route)
    if not travel_dates:
        raise ValueError(f"travel_dates must not be empty for route '{route}'.")

    now_iso = _now_utc_iso()
    travel_dates_json = json.dumps(travel_dates)
    active_int = 1 if active else 0

    sql = """
        INSERT INTO monitored_routes (route, travel_dates, check_every_hours, active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(route) DO UPDATE SET
            travel_dates      = excluded.travel_dates,
            check_every_hours = excluded.check_every_hours,
            active            = excluded.active,
            updated_at        = excluded.updated_at
    """
    try:
        with _write_lock:
            conn = get_connection()
            with conn:
                conn.execute(sql, (
                    route, travel_dates_json, check_every_hours,
                    active_int, now_iso, now_iso,
                ))
    except sqlite3.OperationalError as exc:
        raise DatabaseError(f"Failed to upsert monitored route '{route}': {exc}") from exc

    logger.info(
        '{"level":"INFO","event":"route_upserted","route":"%s","active":%s}',
        route, str(active).lower(),
    )

# ─── READ OPERATIONS ─────────────────────────────────────────────────────────

def get_price_history(
    route: str,
    travel_date: date,
    days_back: int = 90,
    source: Optional[str] = None,
) -> list[PriceObservation]:
    """Return price observations for a route+date within the last N days.

    Args:
        route: Route string.
        travel_date: Travel date to fetch history for.
        days_back: How many days of observations to include (default 90).
        source: Optional source filter.

    Returns:
        List of PriceObservation dataclasses ordered by observed_at ASC.
        Empty list (not exception) if no observations found.
    """
    _validate_route_format(route)
    cutoff = (datetime.now(UTC) - timedelta(days=days_back)).isoformat(timespec="seconds").replace("+00:00", "Z")

    if source is not None:
        if source not in _VALID_SOURCES:
            raise ValueError(f"Invalid source filter '{source}'.")
        sql = """
            SELECT * FROM flight_prices
            WHERE route=? AND travel_date=? AND observed_at >= ? AND source=?
            ORDER BY observed_at ASC
        """
        params: tuple = (route, travel_date.isoformat(), cutoff, source)
    else:
        sql = """
            SELECT * FROM flight_prices
            WHERE route=? AND travel_date=? AND observed_at >= ?
            ORDER BY observed_at ASC
        """
        params = (route, travel_date.isoformat(), cutoff)

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()

    logger.debug(
        '{"level":"DEBUG","event":"price_history_fetched","route":"%s","count":%d}',
        route, len(rows),
    )
    return [_row_to_price_observation(r) for r in rows]


def get_price_stats(route: str, travel_date: date) -> Optional[PriceStats]:
    """Fetch the latest computed statistics for a route+date.

    Args:
        route: Route string.
        travel_date: Travel date.

    Returns:
        PriceStats dataclass if stats exist, None if not yet computed.
    """
    _validate_route_format(route)
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM price_stats WHERE route=? AND travel_date=?",
        (route, travel_date.isoformat()),
    ).fetchone()

    if row is None:
        return None
    return _row_to_price_stats(row)


def get_alert_decision(
    route: str,
    travel_date: date,
    current_price: int,
    min_observations: int = 10,
    alert_percentile_threshold: int = 10,
    cooldown_hours: int = 24,
) -> AlertDecision:
    """Decide whether current_price warrants a Telegram alert.

    Decision logic (first failure exits early):
      1. No stats → should_alert=False
      2. observation_count < min_observations → should_alert=False
      3. current_price > p10_price → should_alert=False
      4. Alert sent within cooldown_hours → should_alert=False
      5. All pass → should_alert=True

    Always populates percentile_rank, pct_below_median, p10_price, all_time_low.

    Args:
        route: Route string.
        travel_date: Travel date to evaluate.
        current_price: Today's scraped price.
        min_observations: Minimum data points before alerting.
        alert_percentile_threshold: Alert if price <= this percentile (default P10).
        cooldown_hours: Hours between alerts for same route+date.

    Returns:
        AlertDecision — ALWAYS returns, never raises.
    """
    def _build(should: bool, reason: str, stats: Optional[PriceStats]) -> AlertDecision:
        p_rank, pct_median, p10, atl, count = None, None, None, None, 0
        if stats:
            count = stats.observation_count
            p10 = stats.p10_price
            atl = stats.all_time_low
            if stats.median_price and stats.median_price > 0:
                pct_median = ((current_price - stats.median_price) / stats.median_price) * 100.0
            p_rank = _compute_percentile_rank(route, travel_date, current_price)
        return AlertDecision(
            should_alert=should, current_price=current_price, reason=reason,
            percentile_rank=p_rank, pct_below_median=pct_median,
            p10_price=p10, all_time_low=atl, observation_count=count,
        )

    try:
        stats = get_price_stats(route, travel_date)
    except Exception:
        stats = None

    if stats is None:
        return _build(False, "No statistics computed yet for this route", None)

    if stats.observation_count < min_observations:
        reason = (
            f"Only {stats.observation_count} observations; "
            f"need {min_observations} minimum"
        )
        return _build(False, reason, stats)

    p10 = stats.p10_price
    if p10 is None or current_price > p10:
        reason = f"Price \u20b9{current_price} is above P10 threshold \u20b9{p10}"
        return _build(False, reason, stats)

    is_cooling, hours_ago = check_alert_cooldown(route, travel_date, cooldown_hours)
    if is_cooling and hours_ago is not None:
        reason = (
            f"Alert already sent {hours_ago:.1f}h ago "
            f"(cooldown: {cooldown_hours}h)"
        )
        return _build(False, reason, stats)

    reason = (
        f"Price \u20b9{current_price} is in P{alert_percentile_threshold} territory "
        f"(threshold: \u20b9{p10})"
    )
    return _build(True, reason, stats)


def _compute_percentile_rank(route: str, travel_date: date, price: int) -> Optional[float]:
    """Return what % of historical prices are ABOVE the given price."""
    conn = get_connection()
    total = conn.execute(
        "SELECT COUNT(*) FROM flight_prices WHERE route=? AND travel_date=?",
        (route, travel_date.isoformat()),
    ).fetchone()[0]
    if not total:
        return None
    above = conn.execute(
        "SELECT COUNT(*) FROM flight_prices WHERE route=? AND travel_date=? AND price_inr > ?",
        (route, travel_date.isoformat(), price),
    ).fetchone()[0]
    return (above / total) * 100.0


def check_alert_cooldown(
    route: str,
    travel_date: date,
    cooldown_hours: int = 24,
) -> tuple[bool, Optional[float]]:
    """Check if a cooldown is active for this route+date.

    Args:
        route: Route string.
        travel_date: Travel date.
        cooldown_hours: Cooldown window in hours.

    Returns:
        Tuple (is_cooling_down, hours_since_last_alert).
        hours_since_last_alert is None if no alert has ever been sent.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT alerted_at FROM alert_log WHERE route=? AND travel_date=? ORDER BY alerted_at DESC LIMIT 1",
        (route, travel_date.isoformat()),
    ).fetchone()

    if row is None:
        return False, None

    alerted_at = datetime.fromisoformat(row["alerted_at"].replace("Z", "+00:00"))
    hours_elapsed = (datetime.now(UTC) - alerted_at).total_seconds() / 3600.0
    return (hours_elapsed < cooldown_hours), hours_elapsed


def get_all_active_routes() -> list[dict]:
    """Return all active routes from monitored_routes.

    Returns:
        List of dicts with keys: route, travel_dates (list[str]), check_every_hours.
        Empty list if no active routes configured.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT route, travel_dates, check_every_hours FROM monitored_routes WHERE active=1"
    ).fetchall()

    result = []
    for r in rows:
        result.append({
            "route": r["route"],
            "travel_dates": json.loads(r["travel_dates"]),
            "check_every_hours": r["check_every_hours"],
        })
    logger.debug('{"level":"DEBUG","event":"active_routes_fetched","count":%d}', len(result))
    return result


def get_latest_ml_forecast(route: str, travel_date: date) -> Optional[MLForecast]:
    """Return the most recent ML forecast for a route+date.

    Args:
        route: Route string.
        travel_date: Travel date.

    Returns:
        MLForecast dataclass or None if no forecast stored yet.
    """
    _validate_route_format(route)
    conn = get_connection()
    row = conn.execute(
        """SELECT * FROM ml_forecasts WHERE route=? AND travel_date=?
           ORDER BY created_at DESC LIMIT 1""",
        (route, travel_date.isoformat()),
    ).fetchone()

    if row is None:
        return None
    return MLForecast(
        route=row["route"],
        travel_date=date.fromisoformat(row["travel_date"]),
        forecast_7d_price=row["forecast_7d_price"],
        forecast_direction=row["forecast_direction"],
        lgbm_score=row["lgbm_score"],
        confidence=row["confidence"],
        model_version=row["model_version"],
        created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
    )


def get_observation_count_by_route() -> dict[str, int]:
    """Return total observation counts grouped by route across all travel dates.

    Returns:
        Dict mapping route -> total observation count.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT route, COUNT(*) AS cnt FROM flight_prices GROUP BY route"
    ).fetchall()
    return {r["route"]: r["cnt"] for r in rows}


def get_recent_alerts(limit: int = 10) -> list[dict]:
    """Return the most recent alerts from alert_log, newest first.

    Args:
        limit: Maximum number of alerts to return.

    Returns:
        List of dicts: route, travel_date, price_notified, alert_reason, alerted_at.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT route, travel_date, price_notified, alert_reason, alerted_at
           FROM alert_log ORDER BY alerted_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ─── PRIVATE ROW MAPPERS ─────────────────────────────────────────────────────

def _row_to_price_observation(row: sqlite3.Row) -> PriceObservation:
    return PriceObservation(
        id=row["id"],
        observed_at=datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00")),
        route=row["route"],
        travel_date=date.fromisoformat(row["travel_date"]),
        price_inr=row["price_inr"],
        airline=row["airline"],
        stops=row["stops"],
        days_advance=row["days_advance"],
        source=row["source"],
    )


def _row_to_price_stats(row: sqlite3.Row) -> PriceStats:
    return PriceStats(
        route=row["route"],
        travel_date=date.fromisoformat(row["travel_date"]),
        p10_price=row["p10_price"],
        p25_price=row["p25_price"],
        median_price=row["median_price"],
        all_time_low=row["all_time_low"],
        all_time_high=row["all_time_high"],
        observation_count=row["observation_count"],
        last_updated=datetime.fromisoformat(row["last_updated"].replace("Z", "+00:00")),
    )
