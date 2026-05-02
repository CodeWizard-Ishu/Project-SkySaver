# Graph Report - .  (2026-05-02)

## Corpus Check
- Corpus is ~5,040 words - fits in a single context window. You may not need a graph.

## Summary
- 142 nodes · 201 edges · 21 communities detected
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.83)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_DB Testing & Mocks|DB Testing & Mocks]]
- [[_COMMUNITY_Project Overview & Tech Stack|Project Overview & Tech Stack]]
- [[_COMMUNITY_Route Configuration & Errors|Route Configuration & Errors]]
- [[_COMMUNITY_Database Initialization|Database Initialization]]
- [[_COMMUNITY_DB Connection & Basic Queries|DB Connection & Basic Queries]]
- [[_COMMUNITY_Alert Logic Testing|Alert Logic Testing]]
- [[_COMMUNITY_Price History & Data Models|Price History & Data Models]]
- [[_COMMUNITY_Alerting & Price Statistics|Alerting & Price Statistics]]
- [[_COMMUNITY_Data Ingestion & Logging|Data Ingestion & Logging]]
- [[_COMMUNITY_Percentile Calculations & Errors|Percentile Calculations & Errors]]
- [[_COMMUNITY_Route Monitoring Tests|Route Monitoring Tests]]
- [[_COMMUNITY_Alert Log Tests|Alert Log Tests]]
- [[_COMMUNITY_ML Forecasts|ML Forecasts]]
- [[_COMMUNITY_Infrastructure & Hosting|Infrastructure & Hosting]]
- [[_COMMUNITY_Cloud Platform|Cloud Platform]]
- [[_COMMUNITY_AI Models (Claude)|AI Models (Claude)]]
- [[_COMMUNITY_AI Models (Gemini)|AI Models (Gemini)]]
- [[_COMMUNITY_Tools (Graphify)|Tools (Graphify)]]
- [[_COMMUNITY_External APIs (Amadeus)|External APIs (Amadeus)]]
- [[_COMMUNITY_Database Engine (SQLite)|Database Engine (SQLite)]]
- [[_COMMUNITY_Database Engine (TimescaleDB)|Database Engine (TimescaleDB)]]

## God Nodes (most connected - your core abstractions)
1. `_insert()` - 19 edges
2. `get_connection()` - 18 edges
3. `DatabaseError` - 11 edges
4. `TestInsertPriceObservation` - 10 edges
5. `TestGetAlertDecision` - 10 edges
6. `_validate_route_format()` - 9 edges
7. `update_price_stats()` - 9 edges
8. `upsert_monitored_route()` - 7 edges
9. `TestUpdatePriceStats` - 7 edges
10. `create_tables()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `create_tables()` --calls--> `get_connection()`  [INFERRED]
  db\init_db.py → db\queries.py
- `verify_schema()` --calls--> `get_connection()`  [INFERRED]
  db\init_db.py → db\queries.py
- `create_tables()` --calls--> `fresh_db()`  [INFERRED]
  db\init_db.py → tests\test_db.py
- `load_routes_from_config()` --calls--> `upsert_monitored_route()`  [INFERRED]
  db\init_db.py → db\queries.py
- `Oracle VPS` --semantically_similar_to--> `Oracle Cloud A1 Always-Free`  [INFERRED] [semantically similar]
  memory-bank/projectbrief.md → memory-bank/techContext.md

## Communities

### Community 0 - "DB Testing & Mocks"
Cohesion: 0.09
Nodes (9): _insert(), tests/test_db.py — Comprehensive pytest suite for db/queries.py and db/init_db.p, Hardcoded 20 prices — P10 must be exactly prices[1] (nearest rank)., Shortcut to insert one observation with sensible defaults., 10 threads each insert 5 rows — total must be 50, no corruption., TestGetObservationCountByRoute, TestGetPriceHistory, TestInsertPriceObservation (+1 more)

### Community 1 - "Project Overview & Tech Stack"
Cohesion: 0.2
Nodes (11): Flight Price AI Agent, Ishu Jaiswal, Nagpur Airport (NAG), Telegram, AG2 (AutoGen), LightGBM, n8n Community Edition, OpenClaw (+3 more)

### Community 2 - "Route Configuration & Errors"
Cohesion: 0.18
Nodes (11): load_routes_from_config(), Parse config/routes.yaml and upsert every route into monitored_routes.      Args, AlertCooldownError, DatabaseError, Base exception for all database layer errors., Raised when querying a route not in monitored_routes., Insert or update a route in monitored_routes registry.      Sets created_at on f, Raised when an alert was already sent within the cooldown period. (+3 more)

### Community 3 - "Database Initialization"
Cohesion: 0.22
Nodes (10): _check_sqlite_version(), create_tables(), _ensure_db_dir_writable(), db/init_db.py — Database initializer for SkySaver.  Run once on first boot (pyth, Create all 5 tables and their indexes. Safe to run multiple times.      Raises:, Check that all 5 tables exist with all expected columns.      Returns:         T, Raise PermissionError if the database directory is not writable., verify_schema() (+2 more)

### Community 4 - "DB Connection & Basic Queries"
Cohesion: 0.18
Nodes (11): _compute_percentile_rank(), get_all_active_routes(), get_connection(), _get_db_path(), get_observation_count_by_route(), get_recent_alerts(), Return the module-level thread-safe SQLite connection (lazy init).      Applies, Return what % of historical prices are ABOVE the given price. (+3 more)

### Community 5 - "Alert Logic Testing"
Cohesion: 0.29
Nodes (1): TestGetAlertDecision

### Community 6 - "Price History & Data Models"
Cohesion: 0.28
Nodes (8): AlertDecision, close_connection(), get_price_history(), PriceObservation, db/queries.py — Complete read/write API for SkySaver flight price database.  Thi, Cleanly close the database connection. Safe to call if never opened.      Called, Return price observations for a route+date within the last N days.      Args:, _row_to_price_observation()

### Community 7 - "Alerting & Price Statistics"
Cohesion: 0.25
Nodes (8): check_alert_cooldown(), get_alert_decision(), get_price_stats(), PriceStats, Fetch the latest computed statistics for a route+date.      Args:         route:, Decide whether current_price warrants a Telegram alert.      Decision logic (fir, Check if a cooldown is active for this route+date.      Args:         route: Rou, _row_to_price_stats()

### Community 8 - "Data Ingestion & Logging"
Cohesion: 0.32
Nodes (8): insert_price_observation(), log_alert_sent(), _now_utc_iso(), Insert one scraped price observation into flight_prices.      Calculates days_ad, Store one ML model prediction. Append-only — never updates existing rows.      A, Record that a Telegram alert was sent. Sets alerted_at to current UTC.      Args, store_ml_forecast(), _validate_route_format()

### Community 9 - "Percentile Calculations & Errors"
Cohesion: 0.33
Nodes (6): InsufficientDataError, _percentile_nearest_rank(), Nearest-rank percentile on a sorted ascending list., Recalculate and upsert price_stats for a route+date pair.      Reads ALL observa, Raised when a route has fewer observations than the minimum required., update_price_stats()

### Community 10 - "Route Monitoring Tests"
Cohesion: 0.33
Nodes (1): TestMonitoredRoutes

### Community 11 - "Alert Log Tests"
Cohesion: 0.4
Nodes (1): TestAlertLog

### Community 12 - "ML Forecasts"
Cohesion: 0.67
Nodes (3): get_latest_ml_forecast(), MLForecast, Return the most recent ML forecast for a route+date.      Args:         route: R

### Community 13 - "Infrastructure & Hosting"
Cohesion: 1.0
Nodes (2): Oracle VPS, Oracle Cloud A1 Always-Free

### Community 14 - "Cloud Platform"
Cohesion: 1.0
Nodes (1): Google Antigravity

### Community 15 - "AI Models (Claude)"
Cohesion: 1.0
Nodes (1): Claude Sonnet 4.6

### Community 16 - "AI Models (Gemini)"
Cohesion: 1.0
Nodes (1): Gemini 2.5 Flash

### Community 17 - "Tools (Graphify)"
Cohesion: 1.0
Nodes (1): Graphify

### Community 18 - "External APIs (Amadeus)"
Cohesion: 1.0
Nodes (1): Amadeus Travel API

### Community 19 - "Database Engine (SQLite)"
Cohesion: 1.0
Nodes (1): SQLite

### Community 20 - "Database Engine (TimescaleDB)"
Cohesion: 1.0
Nodes (1): TimescaleDB

## Knowledge Gaps
- **46 isolated node(s):** `Nagpur Airport (NAG)`, `Ishu Jaiswal`, `Oracle VPS`, `Oracle Cloud A1 Always-Free`, `Google Antigravity` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Alert Logic Testing`** (10 nodes): `TestGetAlertDecision`, `._seed_stats()`, `.test_alert_triggered_correctly()`, `.test_cooldown_blocks_second_alert()`, `.test_cooldown_expires()`, `.test_insufficient_observations()`, `.test_no_stats_yet()`, `.test_pct_below_median_negative()`, `.test_percentile_rank_calculated()`, `.test_price_above_p10()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Route Monitoring Tests`** (6 nodes): `TestMonitoredRoutes`, `.test_empty_travel_dates()`, `.test_invalid_route_format()`, `.test_paused_route_excluded()`, `.test_upsert_new_route()`, `.test_upsert_updates_existing()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Alert Log Tests`** (5 nodes): `TestAlertLog`, `.test_cooldown_check_active()`, `.test_cooldown_check_expired()`, `.test_cooldown_check_no_prior_alert()`, `.test_log_alert_stores_correctly()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Infrastructure & Hosting`** (2 nodes): `Oracle VPS`, `Oracle Cloud A1 Always-Free`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Cloud Platform`** (1 nodes): `Google Antigravity`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `AI Models (Claude)`** (1 nodes): `Claude Sonnet 4.6`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `AI Models (Gemini)`** (1 nodes): `Gemini 2.5 Flash`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tools (Graphify)`** (1 nodes): `Graphify`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `External APIs (Amadeus)`** (1 nodes): `Amadeus Travel API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Database Engine (SQLite)`** (1 nodes): `SQLite`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Database Engine (TimescaleDB)`** (1 nodes): `TimescaleDB`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `create_tables()` connect `Database Initialization` to `DB Connection & Basic Queries`?**
  _High betweenness centrality (0.383) - this node is a cross-community bridge._
- **Why does `get_connection()` connect `DB Connection & Basic Queries` to `Route Configuration & Errors`, `Database Initialization`, `Price History & Data Models`, `Alerting & Price Statistics`, `Data Ingestion & Logging`, `Percentile Calculations & Errors`, `ML Forecasts`?**
  _High betweenness centrality (0.368) - this node is a cross-community bridge._
- **Why does `fresh_db()` connect `Database Initialization` to `DB Testing & Mocks`?**
  _High betweenness centrality (0.361) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `get_connection()` (e.g. with `create_tables()` and `verify_schema()`) actually correct?**
  _`get_connection()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Nagpur Airport (NAG)`, `Ishu Jaiswal`, `Oracle VPS` to the rest of the system?**
  _46 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `DB Testing & Mocks` be split into smaller, more focused modules?**
  _Cohesion score 0.09 - nodes in this community are weakly interconnected._