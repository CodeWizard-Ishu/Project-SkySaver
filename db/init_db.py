"""db/init_db.py — Database initializer for SkySaver.

Run once on first boot (python db/init_db.py) or call create_tables() for
programmatic use. All DDL uses IF NOT EXISTS — safely re-runnable.
Reads DATABASE_PATH from env (fallback: ./db/flight_prices.db).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
from pathlib import Path

# Ensure the project root is on sys.path regardless of how this file is invoked
# (e.g. `python db/init_db.py` only adds db/ to sys.path, not the root).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger("flight_agent.db.init")

_MIN_SQLITE = (3, 35, 0)

# ── DDL Statements ───────────────────────────────────────────────────────────
_TABLES: list[str] = [
    """CREATE TABLE IF NOT EXISTS flight_prices (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        observed_at   TEXT    NOT NULL,
        route         TEXT    NOT NULL,
        travel_date   TEXT    NOT NULL,
        price_inr     INTEGER NOT NULL,
        airline       TEXT    NOT NULL,
        stops         INTEGER NOT NULL DEFAULT 0,
        days_advance  INTEGER NOT NULL,
        source        TEXT    NOT NULL,
        CHECK (price_inr  > 0),
        CHECK (stops     >= 0),
        CHECK (days_advance >= 0),
        CHECK (source IN ('skyscanner','google_flights','amadeus'))
    )""",
    """CREATE TABLE IF NOT EXISTS price_stats (
        route              TEXT    NOT NULL,
        travel_date        TEXT    NOT NULL,
        p10_price          INTEGER,
        p25_price          INTEGER,
        median_price       INTEGER,
        all_time_low       INTEGER,
        all_time_high      INTEGER,
        observation_count  INTEGER NOT NULL DEFAULT 0,
        last_updated       TEXT    NOT NULL,
        PRIMARY KEY (route, travel_date)
    )""",
    """CREATE TABLE IF NOT EXISTS ml_forecasts (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        route              TEXT    NOT NULL,
        travel_date        TEXT    NOT NULL,
        forecast_7d_price  INTEGER,
        forecast_direction TEXT,
        lgbm_score         REAL,
        confidence         REAL,
        model_version      TEXT NOT NULL DEFAULT 'none',
        created_at         TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS alert_log (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        route          TEXT    NOT NULL,
        travel_date    TEXT    NOT NULL,
        price_notified INTEGER NOT NULL,
        alert_reason   TEXT    NOT NULL,
        alerted_at     TEXT    NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS monitored_routes (
        route             TEXT    NOT NULL,
        travel_dates      TEXT    NOT NULL,
        check_every_hours INTEGER NOT NULL DEFAULT 6,
        active            INTEGER NOT NULL DEFAULT 1,
        created_at        TEXT    NOT NULL,
        updated_at        TEXT    NOT NULL,
        PRIMARY KEY (route)
    )""",
]

_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_flight_prices_route_date     ON flight_prices (route, travel_date)",
    "CREATE INDEX IF NOT EXISTS idx_flight_prices_observed_at    ON flight_prices (observed_at)",
    "CREATE INDEX IF NOT EXISTS idx_flight_prices_route_observed ON flight_prices (route, observed_at)",
    "CREATE INDEX IF NOT EXISTS idx_ml_forecasts_route_date      ON ml_forecasts  (route, travel_date, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_alert_log_route_date         ON alert_log     (route, travel_date, alerted_at DESC)",
]

_EXPECTED_COLUMNS: dict[str, set[str]] = {
    "flight_prices":    {"id","observed_at","route","travel_date","price_inr","airline","stops","days_advance","source"},
    "price_stats":      {"route","travel_date","p10_price","p25_price","median_price","all_time_low","all_time_high","observation_count","last_updated"},
    "ml_forecasts":     {"id","route","travel_date","forecast_7d_price","forecast_direction","lgbm_score","confidence","model_version","created_at"},
    "alert_log":        {"id","route","travel_date","price_notified","alert_reason","alerted_at"},
    "monitored_routes": {"route","travel_dates","check_every_hours","active","created_at","updated_at"},
}


# ─── PUBLIC API ──────────────────────────────────────────────────────────────

def create_tables() -> None:
    """Create all 5 tables and their indexes. Safe to run multiple times.

    Raises:
        RuntimeError: If SQLite version < 3.35.0.
        PermissionError: If the database directory is not writable.
    """
    _check_sqlite_version()
    _ensure_db_dir_writable()

    from db.queries import get_connection  # lazy — avoids circular import

    conn = get_connection()
    with conn:
        for stmt in _TABLES:
            conn.execute(stmt)
        for stmt in _INDEXES:
            conn.execute(stmt)
    logger.info("[INIT] Created/verified 5 tables and all indexes")


def load_routes_from_config(config_path: Path | None = None) -> int:
    """Parse config/routes.yaml and upsert every route into monitored_routes.

    Args:
        config_path: Override path; defaults to <project_root>/config/routes.yaml.

    Returns:
        Number of routes successfully loaded.

    Raises:
        FileNotFoundError: If routes.yaml does not exist.
        ValueError: If the YAML structure is malformed.
    """
    import yaml  # PyYAML — only third-party dep in this file
    from db.queries import upsert_monitored_route

    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config" / "routes.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"routes.yaml not found at {config_path}. "
            "Create config/routes.yaml before running init_db."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    if not isinstance(config, dict) or "routes" not in config:
        raise ValueError(
            f"routes.yaml must have a top-level 'routes' list. "
            f"Found keys: {list(config.keys()) if isinstance(config, dict) else type(config)}"
        )

    routes: list[dict] = config["routes"]
    if not isinstance(routes, list):
        raise ValueError("'routes' in routes.yaml must be a list of route objects.")

    count = 0
    for entry in routes:
        upsert_monitored_route(
            route=str(entry["route"]),
            travel_dates=list(entry.get("travel_dates", [])),
            check_every_hours=int(entry.get("check_every_hours", 6)),
            active=bool(entry.get("active", True)),
        )
        count += 1

    logger.info("[INIT] Loaded %d routes from %s", count, config_path)
    return count


def verify_schema() -> bool:
    """Check that all 5 tables exist with all expected columns.

    Returns:
        True if schema is fully correct, False otherwise (errors are logged).
    """
    from db.queries import get_connection

    conn = get_connection()
    all_ok = True
    for table, expected in _EXPECTED_COLUMNS.items():
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
        if not rows:
            logger.error("[VERIFY] Table '%s' missing entirely.", table)
            all_ok = False
            continue
        actual = {r["name"] for r in rows}
        missing = expected - actual
        if missing:
            logger.error("[VERIFY] Table '%s' missing columns: %s", table, missing)
            all_ok = False
    return all_ok


# ─── PRIVATE HELPERS ─────────────────────────────────────────────────────────

def _check_sqlite_version() -> None:
    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < _MIN_SQLITE:
        required = ".".join(str(x) for x in _MIN_SQLITE)
        raise RuntimeError(
            f"SQLite {sqlite3.sqlite_version} is below minimum {required}. "
            "Upgrade SQLite or recompile Python against a newer libsqlite3."
        )


def _ensure_db_dir_writable() -> None:
    """Raise PermissionError if the database directory is not writable."""
    # Read path directly — avoids importing db.queries before sys.path is set.
    db_dir = Path(os.environ.get("DATABASE_PATH", "./db/flight_prices.db")).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    if not os.access(db_dir, os.W_OK):
        raise PermissionError(
            f"Database directory '{db_dir}' is not writable. "
            "Fix filesystem permissions before starting SkySaver."
        )


# ─── ENTRYPOINT ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    db_path = os.environ.get("DATABASE_PATH", "./db/flight_prices.db")
    print(f"[INIT] Database path: {db_path}")

    try:
        _check_sqlite_version()
    except RuntimeError as exc:
        print(f"[INIT] FATAL: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        create_tables()
    except PermissionError as exc:
        print(f"[INIT] FATAL: {exc}", file=sys.stderr)
        sys.exit(1)

    from db.queries import get_connection
    wal_row = get_connection().execute("PRAGMA journal_mode;").fetchone()
    wal_ok = wal_row[0] == "wal" if wal_row else False
    print(f"[INIT] WAL mode: {'enabled' if wal_ok else 'NOT enabled (check pragmas)'}")
    print("[INIT] Created/verified 5 tables")

    try:
        route_count = load_routes_from_config()
        print(f"[INIT] Loaded {route_count} routes from config/routes.yaml")
    except FileNotFoundError as exc:
        print(f"[INIT] WARNING: {exc}", file=sys.stderr)
        print("[INIT] Continuing without routes — add them via the API.")

    if not verify_schema():
        print("[INIT] FATAL: Schema verification failed.", file=sys.stderr)
        sys.exit(1)

    print("[INIT] Database ready.")
